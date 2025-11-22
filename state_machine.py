from enum import Enum
from typing import Dict, Any, List
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)


class BotState(Enum):
    START = "start"
    BOOKING_FLOW = "booking_flow"


class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.state = BotState.START
        self.booking_context: Dict[str, Any] = {}
        self.last_message = ""

    def reset_booking(self):
        """Сброс контекста бронирования"""
        self.booking_context = {}
        self.state = BotState.START
        logger.info(f"Session {self.user_id}: booking reset")


class StateMachine:
    def __init__(self):
        self.sessions: Dict[int, UserSession] = {}

    def get_session(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id)
            logger.info(f"Created new session for user {user_id}")
        return self.sessions[user_id]

    def is_booking_flow(self, message: str) -> bool:
        """Определяем, начался ли процесс бронирования"""
        booking_keywords = [
            'записаться', 'запись', 'бронь', 'стрижк', 'маникюр',
            'окрашивание', 'макияж', 'чистка', 'хочу записаться', 'запишите'
        ]
        return any(keyword in message.lower() for keyword in booking_keywords)

    def process_message(self, user_id: int, message: str, db) -> Dict[str, Any]:
        """Основной метод обработки сообщения"""
        session = self.get_session(user_id)
        session.last_message = message

        logger.info(f"Processing message for user {user_id}: state={session.state}, message='{message}'")

        # Если пользователь в процессе бронирования
        if session.state == BotState.BOOKING_FLOW:
            return self._handle_booking_flow(session, message, db)

        # Если пользователь начинает бронирование
        elif self.is_booking_flow(message):
            logger.info(f"User {user_id} started booking flow")
            session.state = BotState.BOOKING_FLOW
            return self._handle_service_selection(session, db)

        # Не бронирование - передаем в LLM
        else:
            return {"handled": False}

    def _handle_booking_flow(self, session: UserSession, message: str, db) -> Dict[str, Any]:
        """Обработка сообщения в процессе бронирования"""

        # Шаг 1: Выбор услуги
        if 'service' not in session.booking_context:
            return self._handle_service_selection_step(session, message, db)

        # Шаг 2: Выбор мастера
        elif 'master' not in session.booking_context:
            return self._handle_master_selection_step(session, message, db)

        # Шаг 3: Выбор даты
        elif 'date' not in session.booking_context:
            return self._handle_date_selection_step(session, message, db)

        # Шаг 4: Выбор времени
        elif 'time' not in session.booking_context:
            return self._handle_time_selection_step(session, message, db)

        # Шаг 5: Подтверждение
        else:
            return self._handle_confirmation_step(session, message, db)

    def _handle_service_selection(self, session: UserSession, db) -> Dict[str, Any]:
        """Начало выбора услуги"""
        services = db.get_services()
        services_text = "📋 *Выберите услугу:*\n" + "\n".join(
            [f"• {s['name']} - {s['price']} руб." for s in services]
        )

        return {
            "type": "text",
            "text": f"Отлично! Помогу с записью.\n\n{services_text}\n\n*Просто напишите название услуги*",
            "handled": True
        }

    def _handle_service_selection_step(self, session: UserSession, message: str, db) -> Dict[str, Any]:
        """Обработка выбора услуги"""
        logger.info(f"Handling service selection for user {session.user_id}, message: '{message}'")

        services = db.get_services()

        # Ищем услугу по ключевым словам
        for service in services:
            service_name_lower = service['name'].lower()
            message_lower = message.lower()

            # Проверяем совпадение по словам
            service_words = service_name_lower.split()
            if any(word in message_lower for word in service_words):
                session.booking_context['service'] = service
                logger.info(f"User {session.user_id} selected service: {service['name']}")
                logger.info(f"Session state after service selection: {session.state}")
                logger.info(f"Booking context: {session.booking_context}")
                return self._handle_master_selection(session, db)

        # Если услуга не найдена
        logger.info(f"Service not found for message: '{message}'")
        services_text = "📋 *Выберите услугу:*\n" + "\n".join(
            [f"• {s['name']} - {s['price']} руб." for s in services]
        )

        return {
            "type": "text",
            "text": f"Не нашел услугу '{message}'. Пожалуйста, выберите из списка:\n\n{services_text}",
            "handled": True
        }

    def _handle_master_selection(self, session: UserSession, db) -> Dict[str, Any]:
        """Начало выбора мастера"""
        service = session.booking_context['service']
        masters = db.get_available_masters()

        # Фильтруем мастеров по услуге
        suitable_masters = []
        for master in masters:
            if self._is_master_suitable(master, service['category']):
                suitable_masters.append(master)

        if not suitable_masters:
            return {
                "type": "text",
                "text": f"К сожалению, для услуги '{service['name']}' сейчас нет доступных мастеров.",
                "handled": True
            }

        masters_text = "👩‍💼 *Выберите мастера:*\n" + "\n".join(
            [f"• {m['name']} - {m['specialization']}" for m in suitable_masters]
        )

        return {
            "type": "text",
            "text": f"Услуга: *{service['name']}*\n\n{masters_text}",
            "handled": True
        }

    def _handle_master_selection_step(self, session: UserSession, message: str, db) -> Dict[str, Any]:
        """Обработка выбора мастера"""
        masters = db.get_available_masters()
        service = session.booking_context['service']

        # Ищем мастера по имени
        for master in masters:
            if (any(word in message.lower() for word in master['name'].lower().split()) and
                    self._is_master_suitable(master, service['category'])):
                session.booking_context['master'] = master
                logger.info(f"User {session.user_id} selected master: {master['name']}")
                return self._handle_date_selection(session)

        # Если мастер не найден
        return {
            "type": "text",
            "text": f"Мастер '{message}' не найден для услуги '{service['name']}'. Выберите из списка выше.",
            "handled": True
        }

    def _handle_date_selection(self, session: UserSession) -> Dict[str, Any]:
        """Начало выбора даты"""
        dates = self._get_available_dates()
        dates_text = "\n".join([f"• {date}" for date in dates])

        return {
            "type": "text",
            "text": f"Мастер: *{session.booking_context['master']['name']}*\n\n📅 *Выберите дату:*\n{dates_text}",
            "handled": True
        }

    def _handle_date_selection_step(self, session: UserSession, message: str, db) -> Dict[str, Any]:
        """Обработка выбора даты"""
        if re.match(r'\d{4}-\d{2}-\d{2}', message):
            session.booking_context['date'] = message
            logger.info(f"User {session.user_id} selected date: {message}")
            return self._handle_time_selection(session)
        else:
            dates = self._get_available_dates()
            dates_text = "\n".join([f"• {date}" for date in dates])
            return {
                "type": "text",
                "text": f"Пожалуйста, укажите дату в формате ГГГГ-ММ-ДД:\n{dates_text}",
                "handled": True
            }

    def _handle_time_selection(self, session: UserSession) -> Dict[str, Any]:
        """Начало выбора времени"""
        times = ["10:00", "11:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
        times_text = "\n".join([f"• {time}" for time in times])

        return {
            "type": "text",
            "text": f"Дата: *{session.booking_context['date']}*\n\n⏰ *Выберите время:*\n{times_text}",
            "handled": True
        }

    def _handle_time_selection_step(self, session: UserSession, message: str, db) -> Dict[str, Any]:
        """Обработка выбора времени"""
        if re.match(r'\d{2}:\d{2}', message):
            session.booking_context['time'] = message
            logger.info(f"User {session.user_id} selected time: {message}")
            return self._handle_confirmation(session)
        else:
            return {
                "type": "text",
                "text": "Пожалуйста, укажите время в формате ЧЧ:ММ (например, 14:30)",
                "handled": True
            }

    def _handle_confirmation(self, session: UserSession) -> Dict[str, Any]:
        """Подтверждение записи"""
        service = session.booking_context['service']
        master = session.booking_context['master']

        confirm_text = f"""
✅ *Подтвердите запись:*

*Услуга:* {service['name']}
*Мастер:* {master['name']}  
*Дата:* {session.booking_context['date']}
*Время:* {session.booking_context['time']}
*Стоимость:* {service['price']} руб.

Всё верно? (да/нет)
        """

        return {
            "type": "text",
            "text": confirm_text,
            "handled": True
        }

    def _handle_confirmation_step(self, session: UserSession, message: str, db) -> Dict[str, Any]:
        """Обработка подтверждения"""
        if message.lower() in ['да', 'yes', 'ок', 'подтверждаю', 'верно']:
            result = self._create_booking(session, db)
            session.reset_booking()
            return {
                "type": "text",
                "text": result,
                "handled": True
            }
        else:
            session.reset_booking()
            return {
                "type": "text",
                "text": "Запись отменена. Чем еще могу помочь?",
                "handled": True
            }

    def _create_booking(self, session: UserSession, db) -> str:
        """Создание записи в БД"""
        try:
            appointment_id = db.create_appointment(
                session.user_id,
                session.booking_context['master']['id'],
                session.booking_context['service']['id'],
                f"{session.booking_context['date']} {session.booking_context['time']}:00"
            )
            return "🎉 Запись успешно создана! Ждем вас в салоне!"
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return f"❌ Ошибка при создании записи: {str(e)}"

    def _is_master_suitable(self, master: Dict, service_category: str) -> bool:
        """Проверяет подходит ли мастер для услуги"""
        mapping = {
            'Парикмахерские': ['парикмахер', 'стилист'],
            'Косметология': ['косметолог'],
            'Ногтевой сервис': ['маникюр', 'ногтевой'],
            'Визаж': ['визажист']
        }

        for category, keywords in mapping.items():
            if service_category == category:
                return any(keyword in master['specialization'].lower() for keyword in keywords)
        return False

    def _get_available_dates(self) -> List[str]:
        """Ближайшие доступные даты"""
        dates = []
        today = datetime.now()
        for i in range(1, 8):  # неделя вперед
            date = today + timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        return dates