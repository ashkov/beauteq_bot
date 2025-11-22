import logging
from datetime import datetime
from typing import Dict, Any, List

import pytz

from database import Database
from ollama_client import OllamaClient
from simple_rag import SimpleRAG

logger = logging.getLogger(__name__)

from view_router import ViewRouter


class MessageProcessor:
    def __init__(self):
        self.db = Database()
        self.llm = OllamaClient()
        self.rag = SimpleRAG()
        self.view_router = ViewRouter(self.db)
        self.conversation_context = {}  # Только для контекста диалога

    async def process_message(self, user_id: int, user_name: str, user_message: str) -> Dict[str, Any]:
        # self.db.save_conversation(user_id, user_message, False, "message")

        # 1. Получаем релевантные знания из RAG
        rag_results = self.rag.search(user_message)

        # 2. Строим богатый контекст для LLM
        messages = self._build_rich_context(user_id, user_name, user_message, rag_results)
        logger.info(messages)
        # 3. Передаем ВСЕ доступные View в LLM
        available_views = self.view_router.get_available_views()
        response = self.llm.chat(messages, available_views)

        # 4. Обрабатываем ответ LLM
        return await self._handle_llm_response(user_id, user_name, response)

    def _build_rich_context(self, user_id: int, user_name: str, user_message: str, rag_results: List[str]) -> List[
        Dict]:
        """Строит богатый контекст для LLM"""
        messages = []

        # Добавляем историю диалога
        if not user_id in self.conversation_context:
            self.conversation_context[user_id] = self.db.load_conversation(user_id)
        if user_id in self.conversation_context:
            messages.extend(self.conversation_context[user_id][-12:])  # 3 пары вопрос-ответ

        # Системный промпт с информацией о пользователе и салоне
        system_prompt = self._build_system_prompt(user_name, rag_results)
        messages.append({"role": "system", "content": system_prompt})
        # Текущее сообщение пользователя
        messages.append({"role": "user", "content": user_message})
        self.conversation_context[user_id].extend(
            [{"role": "user", "content": user_message}]
        )
        return messages

    def _build_system_prompt(self, user_name: str, rag_results: List[str]) -> str:
        """Строит системный промпт с полной информацией"""
        # Знания из RAG
        rag_text = " Не выясняй тип стрижки, длинну и другие подробности услуг "

        if rag_results:
            rag_text = "📚 *Дополнительная информация:*\n" + "\n".join([rag.get('content') for rag in rag_results])

        months_ru = [
            '', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
            'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
        ]

        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = datetime.now(moscow_tz)
        return f"""
        
{rag_text}

Пользователь: {user_name}. Но может себя называть другим именем. Используй то имя, которое он себе взял в диалоге.

Сейчас: {moscow_time.day} {months_ru[moscow_time.month]} {moscow_time.year} года, {moscow_time.strftime('%H:%M')}, по Москве.
Нельзя записывать на более ранние время и даты, так как это время уже прошло.
"""

    async def _handle_llm_response(self, user_id: int, user_name: str, response: Dict[str, Any]) -> Dict[str, Any]:
        """Обрабатывает ответ от LLM"""

        # Если LLM хочет вызвать View
        if response.get("type") == "function_call":
            view_name = response["function"]
            parameters = response["parameters"]

            # Автоматически добавляем user_id где нужно
            if view_name in ["user_appointments", "create_appointment"]:
                parameters["user_id"] = user_id

            try:
                # Выполняем View
                raw_result = self.view_router.execute_view(view_name, parameters)
                # Рендерим результат
                rendered_result = self.view_router.render_view(view_name, raw_result)

                # Сохраняем в историю
                self._update_conversation_context(user_id, response.get("text", ""), rendered_result)
                self.db.save_conversation(user_id, rendered_result, True, "view_response")

                return {"type": "text", "text": rendered_result}

            except Exception as e:
                error_text = f"❌ Ошибка: {str(e)}"
                self.db.save_conversation(user_id, error_text, True, "error")
                return {"type": "text", "text": error_text}

        # Обычный текстовый ответ
        else:
            self._update_conversation_context(user_id, response.get("text", ""))
            self.db.save_conversation(user_id, response["text"], True, "response")
            return response

    def _update_conversation_context(self, user_id: int, bot_response: str):
        """Обновляет контекст диалога"""
        if user_id not in self.conversation_context:
            self.conversation_context[user_id] = self.db.load_conversation(user_id)

        # Добавляем пару вопрос-ответ
        self.conversation_context[user_id].extend([
            {"role": "assistant", "content": bot_response}
        ])

        # Ограничиваем размер
        if len(self.conversation_context[user_id]) > 10:
            self.conversation_context[user_id] = self.conversation_context[user_id][-10:]
