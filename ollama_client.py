import requests
import json
import logging
from typing import Dict, List, Optional, Any
from config import config

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self.base_url = config.OLLAMA_URL
        self.model = config.OLLAMA_MODEL

    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> Dict[str, Any]:
        """Основной метод общения с Ollama"""

        formatted_messages = self._format_messages(messages, tools)

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": formatted_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_ctx": 8000,
                        "top_p": 0.9
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return self._parse_response(result["response"])
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {"error": "Извините, возникла техническая ошибка. Попробуйте позже."}

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama")
            return {"error": "Сервис временно недоступен. Пожалуйста, попробуйте позже."}
        except Exception as e:
            logger.error(f"Exception in Ollama chat: {str(e)}")
            return {"error": "Внутренняя ошибка ассистента"}

    def _format_messages(self, messages: List[Dict], tools: List[Dict] = None) -> str:
        """Форматируем сообщения в промпт для Ollama"""

        prompt_parts = [f"Системная инструкция: {config.SYSTEM_PROMPT}\n\n"]

        for msg in messages:
            if msg["role"] == "system":
                prompt_parts.append(f"Дополнительная инструкция: {msg['content']}\n")
            elif msg["role"] == "user":
                prompt_parts.append(f"Клиент: {msg['content']}\n")
            elif msg["role"] == "assistant":
                prompt_parts.append(f"Ты: {msg['content']}\n")

        if tools:
            prompt_parts.append("\n\nДОСТУПНЫЕ ФУНКЦИИ:")
            for tool in tools:
                prompt_parts.append(f"- {tool['name']}: {tool['description']}")
                if 'parameters' in tool:
                    params = json.dumps(tool['parameters'], ensure_ascii=False, indent=2)
                    prompt_parts.append(f"  Параметры: {params}")

            prompt_parts.append("""
ФОРМАТ ОТВЕТА:
Если нужно использовать функцию, ответь ТОЛЬКО в формате JSON:
<FUNCTION_CALL>
{
    "function": "имя_функции",
    "parameters": {
        "param1": "value1",
        "param2": "value2"
    }
}
</FUNCTION_CALL>

Иначе отвечай обычным текстом.
""")

        return "\n".join(prompt_parts)

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Парсим ответ от LLM, извлекаем function calls"""

        if "<FUNCTION_CALL>" in response_text and "</FUNCTION_CALL>" in response_text:
            try:
                start = response_text.find("<FUNCTION_CALL>") + len("<FUNCTION_CALL>")
                end = response_text.find("</FUNCTION_CALL>")
                json_str = response_text[start:end].strip()

                function_data = json.loads(json_str)
                return {
                    "type": "function_call",
                    "function": function_data.get("function"),
                    "parameters": function_data.get("parameters", {}),
                    "text": response_text
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse function call: {e}")

        return {
            "type": "text",
            "text": response_text.strip()
        }