import json
import logging
import re
from typing import Dict, List, Any

import requests

from config import config

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = config.OLLAMA_URL
        self.model = config.OLLAMA_MODEL

    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> Dict[str, Any]:
        """Основной метод общения с Ollama с поддержкой function calling"""

        # Форматируем системный промпт с функциями
        system_prompt = self._build_system_prompt(tools)

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

    def _build_system_prompt(self, tools: List[Dict] = None) -> str:
        """Строим системный промпт с четкими инструкциями по выбору одной функции"""

        from datetime import datetime, timedelta

        # Текущая дата для примеров
        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        prompt = f"""
    {config.SYSTEM_PROMPT}

    ДОСТУПНЫЕ МАСТЕРА (используй ТОЛЬКО эти имена):
    - "Анна Ребикова" - Парикмахер-стилист
    - "Мария Иванова" - Косметолог  
    - "Елена Петрова" - Мастер маникюра
    - "Светлана Сидорова" - Визажист

    ДОСТУПНЫЕ УСЛУГИ (используй ТОЛЬКО эти названия):
    - "Стрижка женская", "Стрижка мужская", "Окрашивание" - Парикмахерские
    - "Чистка лица", "Пилинг" - Косметология
    - "Маникюр классический", "Покрытие гель-лак" - Ногтевой сервис  
    - "Вечерний макияж" - Визаж

    ДОСТУПНЫЕ ФУНКЦИИ (ВЫБЕРИ ТОЛЬКО ОДНУ):

    1. get_available_masters - показать мастеров по специализации
       Используй, когда: пользователь спрашивает "кто есть?", "какие мастера?", "к кому записаться?"

    2. get_services - показать услуги и цены  
       Используй, когда: пользователь спрашивает "что делаете?", "какие услуги?", "сколько стоит?"

    3. check_availability - проверить свободное время
       Используй, когда: пользователь УЖЕ выбрал мастера, услугу, дату и время

    4. create_appointment - создать запись
       Используй, когда: пользователь УЖЕ выбрал ВСЕ параметры (мастер, услуга, дата, время)

    ВАЖНЫЕ ПРАВИЛА ВЫБОРА ФУНКЦИИ:
    - В ОДНОМ ответе ТОЛЬКО ОДНА функция
    - Если информации недостаточно - задай уточняющий вопрос текстом
    - Не показывай все функции сразу!

    ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:

    Запрос: "К кому можно записаться?"
    → ТОЛЬКО get_available_masters

    Запрос: "Какие услуги у вас есть?"
    → ТОЛЬКО get_services  

    Запрос: "Хочу записаться к парикмахеру"
    → ТОЛЬКО get_available_masters (специализация: "парикмахер")

    Запрос: "Сколько стоит стрижка?"
    → ТОЛЬКО get_services (категория: "Парикмахерские")

    Запрос: "Свободна ли Анна Ребикова завтра в 15:00?"
    → ТОЛЬКО check_availability

    Запрос: "Запишите меня к Анне на стрижку завтра в 15:00"
    → ТОЛЬКО create_appointment (только если ВСЕ данные есть)

    Запрос: "Хочу записаться" (без деталей)
    → Текстовый ответ: "К какому мастеру вы хотите записаться? У нас есть..."

    ФОРМАТЫ ДАННЫХ:
    - Дата: ГГГГ-ММ-ДД (сегодня: {today.strftime('%Y-%m-%d')}, завтра: {tomorrow.strftime('%Y-%m-%d')})
    - Время: ЧЧ:ММ
    - Специализация: "парикмахер", "косметолог", "маникюр", "визажист"
    - Категория: "Парикмахерские", "Косметология", "Ногтевой сервис", "Визаж"
    """

        prompt += """

    ФОРМАТ ОТВЕТА:
    Если нужно вызвать функцию, отвечай ТОЛЬКО в формате:
    <function_call>
    {
        "function": "имя_функции",
        "parameters": {
            "param1": "value1"
        }
    }
    </function_call>

    Если информации недостаточно - отведи обычным текстом и спроси нужные детали.

    НИКОГДА не показывай все функции сразу!
    НИКОГДА не показывай клиенту формат вызова функций!
    """
        return prompt

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
