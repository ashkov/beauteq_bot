from base_view import BaseView
from database import Database
from typing import Dict, List, Any


class SmartBookingView(BaseView):
    """Умный View для бронирования, который помогает LLM"""

    def __init__(self, db: Database):
        self.db = db

    def get_name(self) -> str:
        return "smart_booking"

    def get_description(self) -> str:
        return "Помочь с записью: найти услуги, мастеров, проверить доступность"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "user_intent": {
                "type": "string",
                "description": "намерение пользователя (выбор_услуги, выбор_мастера, проверка_доступности, создание_записи)",
                "required": True
            },
            "service_preference": {"type": "string", "required": False},
            "master_preference": {"type": "string", "required": False},
            "date_preference": {"type": "string", "required": False},
            "time_preference": {"type": "string", "required": False},
            "user_id": {"type": "integer", "required": False}
        }

    def execute(self, user_intent: str, service_preference: str = None,
                master_preference: str = None, date_preference: str = None,
                time_preference: str = None, user_id: int = None) -> Dict:

        if user_intent == "выбор_услуги":
            services = self.db.get_services()
            if service_preference:
                # Фильтруем по предпочтению
                filtered_services = [s for s in services if service_preference.lower() in s['name'].lower()]
                return {"intent": "service_selection", "services": filtered_services or services}
            return {"intent": "service_selection", "services": services}

        elif user_intent == "выбор_мастера":
            masters = self.db.get_available_masters()
            if service_preference:
                # Фильтруем мастеров по услуге
                suitable_masters = []
                for master in masters:
                    if self._is_master_suitable(master, service_preference):
                        suitable_masters.append(master)
                return {"intent": "master_selection", "masters": suitable_masters}
            return {"intent": "master_selection", "masters": masters}

        elif user_intent == "создание_записи":
            # Полная логика создания записи
            return self._create_appointment(service_preference, master_preference, date_preference, time_preference,
                                            user_id)

        return {"error": "Неизвестное намерение"}

    def render(self, result: Dict, **kwargs) -> str:
        intent = result.get("intent")

        if intent == "service_selection":
            services = result.get("services", [])
            text = "💇 *Доступные услуги:*\n\n"
            for service in services:
                text += f"*{service['name']}* - {service['price']} руб. ({service['duration_minutes']} мин.)\n"
            return text

        elif intent == "master_selection":
            masters = result.get("masters", [])
            text = "👩‍💼 *Доступные мастера:*\n\n"
            for master in masters:
                text += f"*{master['name']}* - {master['specialization']}\n"
            return text

        # ... остальной рендеринг

        return str(result)

class MastersListView(BaseView):
    """View для списка мастеров (аналог MastersListView в Django)"""

    def __init__(self, db: Database):
        self.db = db

    def get_name(self) -> str:
        return "masters_list"

    def get_description(self) -> str:
        return "Получить список доступных мастеров по специализации"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "specialization": {
                "type": "string",
                "description": "специализация (парикмахер, косметолог, маникюр, визажист)",
                "required": False
            }
        }

    def execute(self, specialization: str = None) -> List[Dict]:
        """GET-запрос для получения мастеров"""
        return self.db.get_available_masters(specialization)

    def render(self, result: List[Dict], **kwargs) -> str:
        """Рендерим список мастеров"""
        if not result:
            return "👩‍💼 К сожалению, сейчас нет доступных мастеров."

        text = "👩‍💼 *Доступные мастера:*\n\n"
        for master in result:
            text += f"*{master['name']}* - {master['specialization']}\n"

        return text


class ServicesListView(BaseView):
    """View для списка услуг"""

    def __init__(self, db: Database):
        self.db = db

    def get_name(self) -> str:
        return "services_list"

    def get_description(self) -> str:
        return "Получить список услуг по категории"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "category": {
                "type": "string",
                "description": "категория услуг (парикмахерские, косметология, ногтевой сервис, визаж)",
                "required": False
            }
        }

    def execute(self, category: str = None) -> List[Dict]:
        return self.db.get_services(category)

    def render(self, result: List[Dict], **kwargs) -> str:
        if not result:
            return "💇 Услуги не найдены."

        text = "💇 *Наши услуги и цены:*\n\n"
        for service in result:
            text += f"*{service['name']}* - {service['price']} руб. ({service['duration_minutes']} мин.)\n"

        return text


class UserAppointmentsView(BaseView):
    """View для записей пользователя"""

    def __init__(self, db: Database):
        self.db = db

    def get_name(self) -> str:
        return "user_appointments"

    def get_description(self) -> str:
        return "Получить записи пользователя"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "user_id": {
                "type": "integer",
                "description": "ID пользователя",
                "required": True
            }
        }

    def execute(self, user_id: int) -> List[Dict]:
        return self.db.get_user_appointments(user_id)

    def render(self, result: List[Dict], **kwargs) -> str:
        if not result:
            return "📋 У вас пока нет записей."

        text = "📋 *Ваши записи:*\n\n"
        for appointment in result:
            text += f"*{appointment['master_name']}* - {appointment['service_name']}\n"
            text += f"📅 {appointment['appointment_date']}\n"
            text += f"💵 {appointment['price']} руб.\n"
            text += f"Статус: {appointment['status']}\n\n"

        return text


class CreateAppointmentView(BaseView):
    """View для создания записи (аналог CreateView в Django)"""

    def __init__(self, db: Database):
        self.db = db

    def get_name(self) -> str:
        return "create_appointment"

    def get_description(self) -> str:
        return "Создать запись к мастеру"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "master_name": {"type": "string", "required": True},
            "service_name": {"type": "string", "required": True},
            "date": {"type": "string", "required": True},
            "time": {"type": "string", "required": True},
            "user_id": {"type": "integer", "required": True}
        }

    def execute(self, master_name: str, service_name: str, date: str, time: str, user_id: int) -> Dict:
        # POST-запрос для создания записи
        masters = self.db.get_available_masters()
        services = self.db.get_services()

        master = next((m for m in masters if master_name.lower() in m['name'].lower()), None)
        service = next((s for s in services if service_name.lower() in s['name'].lower()), None)

        if not master:
            return {"success": False, "error": "Мастер не найден"}
        if not service:
            return {"success": False, "error": "Услуга не найдена"}

        appointment_datetime = f"{date} {time}:00"
        appointment_id = self.db.create_appointment(user_id, master['id'], service['id'], appointment_datetime)

        return {
            "success": True,
            "appointment_id": appointment_id,
            "master": master['name'],
            "service": service['name'],
            "date": date,
            "time": time,
            "price": service['price']
        }

    def render(self, result: Dict, **kwargs) -> str:
        if result.get("success"):
            return f"""
✅ *Запись успешно создана!*

*Мастер:* {result['master']}
*Услуга:* {result['service']}  
*Дата:* {result['date']}
*Время:* {result['time']}
*Стоимость:* {result['price']} руб.

Ждем вас в салоне! 🎉
            """
        else:
            return f"❌ Не удалось создать запись: {result.get('error', 'Неизвестная ошибка')}"