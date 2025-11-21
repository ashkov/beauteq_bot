from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import Database
from ollama_client import OllamaClient
import logging

logger = logging.getLogger(__name__)


class BookingSystem:
    def __init__(self):
        self.db = Database()
        self.llm = OllamaClient()

        self.available_functions = [
            {
                "name": "get_available_masters",
                "description": "Получить список доступных мастеров по специализации",
                "parameters": {
                    "specialization": "специализация (парикмахер, косметолог, маникюр, визажист)"
                }
            },
            {
                "name": "get_services",
                "description": "Получить список услуг по категории", 
                "parameters": {
                    "category": "категория услуг (парикмахерские, косметология, ногтевой сервис, визаж)"
                }
            },
            {
                "name": "check_availability",
                "description": "Проверить доступность мастера на определенную дату и время",
                "parameters": {
                    "master_name": "имя мастера",
                    "date": "дата в формате ГГГГ-ММ-ДД (например: 2024-01-15)",
                    "time": "время в формате ЧЧ:ММ (например: 14:30)"
                }
            },
            {
                "name": "create_appointment", 
                "description": "Создать запись к мастеру",
                "parameters": {
                    "master_name": "имя мастера",
                    "service_name": "название услуги",
                    "date": "дата в формате ГГГГ-ММ-ДД (например: 2024-01-15)", 
                    "time": "время в формате ЧЧ:ММ (например: 14:30)",
                    "client_name": "имя клиента"
                }
            }
        ]

    def get_available_masters(self, specialization: str = None) -> List[Dict]:
        """Получить мастеров по специализации"""
        return self.db.get_available_masters(specialization)

    def get_services(self, category: str = None) -> List[Dict]:
        """Получить услуги по категории"""
        return self.db.get_services(category)

    def check_availability(self, master_name: str, date: str, time: str) -> Dict:
        """Проверить доступность мастера"""
        try:
            masters = self.db.get_available_masters()
            master = next((m for m in masters if master_name.lower() in m['name'].lower()), None)

            if not master:
                return {"available": False, "reason": "Мастер не найден"}

            # Проверяем рабочее время
            if not self._is_working_hours(date, time):
                return {"available": False, "reason": "Вне рабочего времени салона"}

            is_available = self.db.check_availability(master['id'], date, time)

            return {
                "available": is_available,
                "reason": "Свободно" if is_available else "Занято", 
                "master": master['name']
            }

        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {"available": False, "reason": f"Ошибка: {str(e)}"}

    def create_appointment(self, master_name: str, service_name: str, date: str,
                           time: str, client_name: str, user_id: int) -> Dict:
        """Создать запись"""
        try:
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
            appointment_datetime = f"{date} {time}:00"
            availability = self.check_availability(master_name, date, time)
            if not availability["available"]:
                return {"success": False, "error": availability["reason"]}

            # Создаем запись
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

        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return {"success": False, "error": str(e)}

    def _is_working_hours(self, date: str, time: str) -> bool:
        """Проверяем рабочее время салона"""
        try:
            dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            hour = dt.hour
            weekday = dt.weekday()

            if weekday < 5:  # Пн-Пт
                return 9 <= hour < 21
            else:  # Сб-Вс
                return 10 <= hour < 20
        except:
            return False

    def process_booking_request(self, user_message: str, user_id: int, user_name: str) -> Dict:
        """Обработать запрос на бронирование - просто передаем в LLM"""
        messages = [{"role": "user", "content": user_message}]
        return self.llm.chat(messages, self.available_functions)