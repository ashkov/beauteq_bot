import json
import logging
import re
from typing import Dict, List, Any

import requests

from config import config

logger = logging.getLogger(__name__)
import inspect
from function_provider import FunctionProvider


class OllamaClient:
    def __init__(self):
        self.base_url = config.OLLAMA_URL
        self.model = config.OLLAMA_MODEL
        self.function_provider = FunctionProvider()
        self.available_functions = self._get_available_functions()

    def _get_available_functions(self) -> List[Dict]:
        """Автоматически получает список функций из FunctionProvider с правильными параметрами"""
        functions = []

        for name, method in inspect.getmembers(self.function_provider, predicate=inspect.ismethod):
            if not name.startswith('_'):  # Публичные методы
                docstring = method.__doc__ or ""
                signature = inspect.signature(method)

                # Парсим описание из docstring (первая строка до Args)
                description = ""
                for line in docstring.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('Args:'):
                        description += line + " "
                    else:
                        break

                # Получаем параметры из аннотаций
                parameters = {}
                for param_name, param in signature.parameters.items():
                    if param_name not in ['self', 'user_id']:  # Исключаем служебные параметры
                        param_info = {
                            "type": self._get_parameter_type(param.annotation),
                            "description": self._extract_param_description(docstring, param_name)
                        }

                        # Если параметр не обязательный
                        if param.default == inspect.Parameter.empty:
                            param_info["required"] = True
                        else:
                            param_info["required"] = False
                            param_info["default"] = param.default

                        parameters[param_name] = param_info

                functions.append({
                    "name": name,
                    "description": description.strip(),
                    "parameters": parameters
                })

        return functions

    def _get_parameter_type(self, annotation) -> str:
        """Преобразует аннотации Python в типы для LLM"""
        if annotation == str:
            return "string"
        elif annotation == int:
            return "integer"
        elif annotation == bool:
            return "boolean"
        elif annotation == List[Dict]:
            return "array"
        else:
            return "string"

    def _extract_param_description(self, docstring: str, param_name: str) -> str:
        """Извлекает описание параметра из docstring"""
        lines = docstring.split('\n')
        in_args = False

        for line in lines:
            line = line.strip()
            if line.startswith('Args:'):
                in_args = True
                continue
            if in_args and line.startswith(param_name + ':'):
                return line.replace(f'{param_name}:', '').strip()

        return ""

    def _build_system_prompt(self, tools: List[Dict] = None) -> str:
        """Автоматически строим системный промпт из реальных данных"""

        # Получаем актуальные данные из БД
        masters = self.function_provider.get_available_masters()
        services = self.function_provider.get_services()

        # Форматируем мастеров
        masters_text = "ДОСТУПНЫЕ МАСТЕРА (используй ТОЛЬКО эти имена):\n"
        for master in masters:
            masters_text += f'- "{master["name"]}" - {master["specialization"]}\n'

        # Форматируем услуги по категориям
        services_by_category = {}
        for service in services:
            category = service["category"]
            if category not in services_by_category:
                services_by_category[category] = []
            services_by_category[category].append(service)

        services_text = "ДОСТУПНЫЕ УСЛУГИ (используй ТОЛЬКО эти названия):\n"
        for category, category_services in services_by_category.items():
            services_text += f"\n{category}:\n"
            for service in category_services:
                services_text += f'- "{service["name"]}" - {service["price"]} руб. ({service["duration_minutes"]} мин.)\n'

        # Форматируем функции
        functions_text = "ДОСТУПНЫЕ ФУНКЦИИ:\n"
        for tool in tools:
            functions_text += f"\n{tool['name']}: {tool['description']}\n"
            if tool['parameters']:
                functions_text += "Параметры:\n"
                for param_name, param_info in tool['parameters'].items():
                    required = " (обязательный)" if param_info.get('required', False) else " (опциональный)"
                    functions_text += f"  - {param_name}: {param_info['type']}{required} - {param_info.get('description', '')}\n"

        prompt = f"""
    {config.SYSTEM_PROMPT}

    {masters_text}

    {services_text}

    {functions_text}

    ПРАВИЛА ИСПОЛЬЗОВАНИЯ ФУНКЦИЙ:
    - Используй ТОЛЬКО имена мастеров и услуг из списков выше
    - Для даты используй формат ГГГГ-ММ-ДД
    - Для времени используй формат ЧЧ:ММ
    - Если информации недостаточно - спроси уточняющие вопросы
    - Правила о формате даты и времени относятся к вызову функций. Не проси пользователей его придерживаться
    ВАЖНЫЕ ПРАВИЛА ВЫЗОВА ФУНКЦИЙ:
    - НЕ вызывай функции, если не все обязательные параметры введены
    - Если данных недостаточно - спроси уточняющие вопросы текстом
    ФОРМАТ ОТВЕТА:
    Если нужно вызвать функцию, отвечай ТОЛЬКО в формате:
    <function_call>
    {{
        "function": "имя_функции",
        "parameters": {{
            "param1": "value1",
            "param2": "value2"
        }}
    }}
    </function_call>
    Обрати внимание! корневой тег у функции это <function_call>. Не надо его исправлять, 
    и подставлять вместо строки function_call название функции
    
    НИКОГДА не показывай клиенту формат вызова функций!
    """
        return prompt

    def execute_function(self, function_name: str, parameters: Dict, user_id: int = None) -> Any:
        """Выполняет функцию по имени"""
        if not hasattr(self.function_provider, function_name):
            raise ValueError(f"Неизвестная функция: {function_name}")

        method = getattr(self.function_provider, function_name)
        signature = inspect.signature(method)

        # Фильтруем параметры - оставляем только те, что есть в сигнатуре метода
        valid_params = {}
        for param_name in signature.parameters:
            if param_name in parameters:
                valid_params[param_name] = parameters[param_name]
            elif param_name == 'user_id' and user_id is not None:
                valid_params[param_name] = user_id

        return method(**valid_params)

    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> Dict[str, Any]:
        """Основной метод общения с Ollama с поддержкой function calling"""

        # Форматируем системный промпт с функциями
        system_prompt = self._build_system_prompt(tools)
        logger.info(system_prompt)

        # Собираем все сообщения включая системный промпт
        all_messages = [{"role": "system", "content": system_prompt}]
        all_messages.extend(messages)

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": all_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 8000,
                        "top_p": 0.9
                    }
                },
                timeout=200
            )

            if response.status_code == 200:
                result = response.json()
                message_content = result["message"]["content"]
                return self._parse_response(message_content)
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {"type": "text", "text": "Извините, возникла техническая ошибка. Попробуйте позже."}

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama")
            return {"type": "text", "text": "Сервис временно недоступен. Пожалуйста, попробуйте позже."}
        except Exception as e:
            logger.error(f"Exception in Ollama chat: {str(e)}")
            return {"type": "text", "text": "Внутренняя ошибка ассистента"}


    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Парсим ответ и извлекаем function calls"""

        # Очищаем текст от лишних пробелов
        response_text = response_text.strip()
        logger.info(response_text)

        # Пытаемся найти function call
        function_call_match = re.search(
            r'<function_call>(.*?)</function_call>',
            response_text,
            re.DOTALL
        )

        if function_call_match:
            try:
                json_str = function_call_match.group(1).strip()
                function_data = json.loads(json_str)

                # Логируем для отладки
                logger.info(f"Parsed function call: {function_data}")

                return {
                    "type": "function_call",
                    "function": function_data.get("function"),
                    "parameters": function_data.get("parameters", {})
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse function call JSON: {e}")
                logger.error(f"Raw JSON string: {json_str}")
                # Если не удалось распарсить, возвращаем как текст
                return {"type": "text", "text": response_text}

        # Если function call не найден, возвращаем как текст
        return {"type": "text", "text": response_text}
