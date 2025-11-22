import logging
from typing import Dict, List, Any
from database import Database
from datetime import datetime

logger = logging.getLogger(__name__)

from typing import Dict, List, Optional


class FunctionProvider:
    def __init__(self):
        self.db = Database()

    def get_available_masters(self, specialization: Optional[str] = None) -> List[Dict]:
        """Получить список доступных мастеров по специализации

        Args:
            specialization: специализация мастера
        """
        return self.db.get_available_masters(specialization)

    def get_services(self, category: Optional[str] = None) -> List[Dict]:
        """Получить список услуг по категории
        Args:
            category: категория услуг
        """
        return self.db.get_services(category)

    def check_availability(self, master_name: str, date: str, time: str) -> Dict:
        """Проверить доступность мастера на определенную дату и время
        Эта функция вызывается только если предоставлена дата и время

        Args:
            master_name: имя мастера для проверки доступности
            date: дата для проверки в формате ГГГГ-ММ-ДД
            time: время для проверки в формате ЧЧ:ММ
        """
        masters = self.db.get_available_masters()
        master = next((m for m in masters if master_name.lower() in m['name'].lower()), None)

        if not master:
            return {"available": False, "reason": "Мастер не найден"}

        is_available = self.db.check_availability(master['id'], date, time)
        return {
            "available": is_available,
            "reason": "Свободно" if is_available else "Занято",
            "master": master['name']
        }

    def create_appointment(self, master_name: str, service_name: str, date: str,
                           time: str, client_name: str, user_id: int) -> Dict:
        """Создать запись к мастеру

        Args:
            master_name: имя мастера для записи
            service_name: название услуги для записи
            date: дата записи в формате ГГГГ-ММ-ДД
            time: время записи в формате ЧЧ:ММ
            client_name: имя клиента для записи
            user_id: идентификатор пользователя в системе
        """
        # Находим мастера
        masters = self.db.get_available_masters()
        master = next((m for m in masters if master_name.lower() in m['name'].lower()), None)
        if not master:
            return {"success": False, "error": "Мастер не найден"}

        # Находим услугу
        services = self.db.get_services()
        service = next((s for s in services if service_name.lower() in s['name'].lower()), None)
        if not service:
            return {"success": False, "error": "Услуга не найдена"}

        # Проверяем доступность
        availability = self.check_availability(master_name, date, time)
        if not availability["available"]:
            return {"success": False, "error": availability["reason"]}

        # Создаем запись
        appointment_datetime = f"{date} {time}:00"
        appointment_id = self.db.create_appointment(
            user_id, master['id'], service['id'], appointment_datetime
        )

        return {
            "success": True,
            "appointment_id": appointment_id,
            "master": master['name'],
            "service": service['name'],
            "date": date,
            "time": time,
            "price": service['price']
        }

    def get_user_appointments(self, user_id: int) -> List[Dict]:
        """Получить записи пользователя

        Args:
            user_id: ID пользователя в системе
        """
        return self.db.get_user_appointments(user_id)

    # Или если нужно по имени клиента:
    def get_appointments_by_client_name(self, client_name: str) -> List[Dict]:
        """Получить записи по имени клиента

        Args:
            client_name: имя клиента для поиска записей
        """
        # Эта функция сложнее - нужно искать по имени в БД
        # Пока лучше использовать get_user_appointments
        return []