import logging
from typing import Dict, Any, List
from database import Database
from booking_system import BookingSystem
from ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class MessageProcessor:
    def __init__(self):
        self.db = Database()
        self.booking_system = BookingSystem()
        self.llm = OllamaClient()

    async def process_message(self, user_id: int, user_name: str, user_message: str) -> Dict[str, Any]:
        """Основной метод обработки сообщений"""

        # Сохраняем сообщение пользователя
        self.db.save_user(user_id, "", user_name)
        self.db.save_conversation(user_id, user_message, False, "message")

        try:
            # Определяем, относится ли сообщение к бронированию
            is_booking_related = any(word in user_message.lower() for word in [
                'записаться', 'запись', 'бронь', 'стрижк', 'мастер', 'услуг',
                'стоит', 'цена', 'цен', 'price', 'cost', 'available', 'время',
                'свободн', 'расписан', 'запишите', 'хочу записаться'
            ])

            if is_booking_related:
                return await self._process_booking_message(user_id, user_name, user_message)
            else:
                return await self._process_general_message(user_id, user_message)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {"type": "text", "text": "Извините, произошла ошибка. Пожалуйста, попробуйте позже."}

    async def _process_booking_message(self, user_id: int, user_name: str, user_message: str) -> Dict[str, Any]:
        """Обработка сообщений, связанных с бронированием"""

        # Получаем ответ от LLM
        messages = [{"role": "user", "content": user_message}]
        response = self.llm.chat(messages, self.booking_system.available_functions)

        # Логируем ответ для отладки
        logger.info(f"LLM response for '{user_message}': {response}")

        # Если LLM хочет вызвать функцию - выполняем её
        if response.get("type") == "function_call":
            return await self._execute_function_call(
                response["function"],
                response["parameters"],
                user_id,
                user_name
            )
        else:
            # Просто возвращаем текстовый ответ
            self.db.save_conversation(user_id, response["text"], True, "response")
            return response

    async def _execute_function_call(self, function_name: str, parameters: Dict,
                                     user_id: int, user_name: str) -> Dict[str, Any]:
        """Выполняет вызов функции и возвращает результат"""

        logger.info(f"Executing function: {function_name} with params: {parameters}")

        try:
            # Для create_appointment добавляем user_id и исправляем client_name
            if function_name == "create_appointment":
                if "client_name" in parameters and parameters["client_name"].strip().lower() in ["me", "я", "myself",
                                                                                                 "меня"]:
                    parameters["client_name"] = user_name
                parameters["user_id"] = user_id

            if function_name == "get_available_masters":
                specialization = parameters.get("specialization", "")
                result = self.booking_system.get_available_masters(specialization)

                if result:
                    masters_text = "👩‍💼 *Доступные мастера:*\n\n"
                    for master in result:
                        masters_text += f"*{master['name']}* - {master['specialization']}\n"

                    self.db.save_conversation(user_id, masters_text, True, "masters_list")
                    return {"type": "text", "text": masters_text}
                else:
                    text = "К сожалению, сейчас нет доступных мастеров по этой специализации."
                    self.db.save_conversation(user_id, text, True, "masters_list")
                    return {"type": "text", "text": text}

            elif function_name == "get_services":
                category = parameters.get("category", "")
                result = self.booking_system.get_services(category)

                if result:
                    services_text = "💇 *Наши услуги и цены:*\n\n"
                    for service in result:
                        services_text += f"*{service['name']}* - {service['price']} руб. ({service['duration_minutes']} мин.)\n"

                    self.db.save_conversation(user_id, services_text, True, "services_list")
                    return {"type": "text", "text": services_text}
                else:
                    text = "К сожалению, услуги по этой категории не найдены."
                    self.db.save_conversation(user_id, text, True, "services_list")
                    return {"type": "text", "text": text}

            elif function_name == "check_availability":
                result = self.booking_system.check_availability(**parameters)

                if result.get("available"):
                    text = f"✅ {result['master']} свободен в это время!"
                else:
                    text = f"❌ {result['reason']}"

                self.db.save_conversation(user_id, text, True, "availability_check")
                return {"type": "text", "text": text}

            elif function_name == "create_appointment":
                result = self.booking_system.create_appointment(**parameters)

                if result.get("success"):
                    appointment_text = f"""
    ✅ *Запись успешно создана!*

    *Мастер:* {result['master']}
    *Услуга:* {result['service']}  
    *Дата:* {result['date']}
    *Время:* {result['time']}
    *Стоимость:* {result['price']} руб.

    💡 Пожалуйста, приходите за 10 минут до записи.

    Ждем вас в салоне Beauteq! 🎉
                    """
                    self.db.save_conversation(user_id, appointment_text, True, "appointment_created")
                    return {"type": "text", "text": appointment_text}
                else:
                    error_text = f"❌ Не удалось создать запись: {result.get('error', 'Неизвестная ошибка')}"
                    self.db.save_conversation(user_id, error_text, True, "appointment_error")
                    return {"type": "text", "text": error_text}

            else:
                text = f"Неизвестная функция: {function_name}"
                self.db.save_conversation(user_id, text, True, "error")
                return {"type": "text", "text": text}

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            error_text = "Извините, произошла ошибка при обработке запроса."
            self.db.save_conversation(user_id, error_text, True, "error")
            return {"type": "text", "text": error_text}

    async def _validate_appointment_params(self, params: Dict, user_name: str) -> Dict:
        """Валидация параметров записи"""

        # Исправляем имя клиента
        if "client_name" in params and params["client_name"].strip().lower() in ["me", "я", "myself", "меня"]:
            params["client_name"] = user_name

        # Проверяем дату
        date = params.get("date", "").strip()
        if not date or date.lower() in ["today()", "now()", "сегодня", "завтра", "today", "now"]:
            suggestion = await self._suggest_datetime_format()
            return {
                "error": f"❌ Пожалуйста, укажите конкретную дату в формате ГГГГ-ММ-ДД.\n\n{suggestion}"
            }

        # Проверяем время
        time = params.get("time", "").strip()
        if not time or time.lower() in ["now()", "сейчас", "now"]:
            suggestion = await self._suggest_datetime_format()
            return {
                "error": f"❌ Пожалуйста, укажите конкретное время в формате ЧЧ:ММ.\n\n{suggestion}"
            }

        # Проверяем мастера
        master_name = params.get("master_name", "").strip()
        available_masters = self.booking_system.get_available_masters()
        master_names = [m["name"] for m in available_masters]

        # Исправляем опечатки в имени мастера
        corrected_master = None
        for master in master_names:
            if master_name.lower() in master.lower() or master.lower() in master_name.lower():
                corrected_master = master
                break

        if not corrected_master:
            masters_list = "\n".join([f"• {m}" for m in master_names])
            return {
                "error": f"❌ Мастер '{master_name}' не найден. Доступные мастера:\n{masters_list}"
            }

        params["master_name"] = corrected_master

        # Проверяем услугу
        service_name = params.get("service_name", "").strip()
        available_services = self.booking_system.get_services()
        service_names = [s["name"] for s in available_services]

        # Исправляем опечатки в услуге
        corrected_service = None
        for service in service_names:
            if service_name.lower() in service.lower() or service.lower() in service_name.lower():
                corrected_service = service
                break

        if not corrected_service:
            services_list = "\n".join([f"• {s}" for s in service_names])
            return {
                "error": f"❌ Услуга '{service_name}' не найдена. Доступные услуги:\n{services_list}"
            }

        params["service_name"] = corrected_service

        return {"params": params}

    async def _suggest_datetime_format(self) -> str:
        """Возвращает подсказку о формате даты и времени"""
        from datetime import datetime, timedelta

        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        return f"""
📅 Подсказка по формату:
- Сегодня: {today.strftime('%Y-%m-%d')}
- Завтра: {tomorrow.strftime('%Y-%m-%d')}  
- Пример времени: 14:30, 09:00, 18:45

Пожалуйста, укажите дату и время в правильном формате!
"""

    async def _process_general_message(self, user_id: int, user_message: str) -> Dict[str, Any]:
        """Обработка общих сообщений"""
        response = self.llm.chat([{"role": "user", "content": user_message}])
        self.db.save_conversation(user_id, response["text"], True, "response")
        return response