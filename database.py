import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "beauteq.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            # Таблица пользователей
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица мастеров
            conn.execute("""
                CREATE TABLE IF NOT EXISTS masters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    specialization TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

            # Таблица услуг
            conn.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    duration_minutes INTEGER,
                    price DECIMAL(10,2)
                )
            """)

            # Таблица записей
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    master_id INTEGER,
                    service_id INTEGER,
                    appointment_date TIMESTAMP,
                    status TEXT DEFAULT 'booked',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (master_id) REFERENCES masters (id),
                    FOREIGN KEY (service_id) REFERENCES services (id)
                )
            """)

            # Таблица диалогов
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message TEXT,
                    is_bot BOOLEAN,
                    intent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Наполняем начальными данными
            self._seed_initial_data(conn)

            conn.commit()

    def _seed_initial_data(self, conn):
        """Начальные данные салона"""
        # Мастера
        masters = [
            ("Анна Ребикова", "Парикмахер-стилист"),
            ("Мария Иванова", "Косметолог"),
            ("Елена Петрова", "Мастер маникюра"),
            ("Светлана Сидорова", "Визажист")
        ]

        conn.executemany(
            "INSERT OR IGNORE INTO masters (name, specialization) VALUES (?, ?)",
            masters
        )

        # Услуги
        services = [
            ("Стрижка женская", "Парикмахерские", 60, 2000),
            ("Стрижка мужская", "Парикмахерские", 30, 1000),
            ("Окрашивание", "Парикмахерские", 120, 3500),
            ("Чистка лица", "Косметология", 90, 3500),
            ("Пилинг", "Косметология", 60, 2500),
            ("Маникюр классический", "Ногтевой сервис", 60, 1500),
            ("Покрытие гель-лак", "Ногтевой сервис", 90, 2000),
            ("Вечерний макияж", "Визаж", 60, 3000)
        ]

        conn.executemany(
            "INSERT OR IGNORE INTO services (name, category, duration_minutes, price) VALUES (?, ?, ?, ?)",
            services
        )

    def save_user(self, user_id: int, username: str, first_name: str):
        """Сохраняем пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )

    def save_conversation(self, user_id: int, message: str, is_bot: bool, intent: str = ""):
        """Сохраняем сообщение в историю"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (user_id, message, is_bot, intent) VALUES (?, ?, ?, ?)",
                (user_id, message, is_bot, intent)
            )

    def get_available_masters(self, specialization: str = None) -> List[Dict]:
        """Получить список мастеров"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if specialization:
                cursor = conn.execute(
                    "SELECT * FROM masters WHERE specialization LIKE ? AND is_active = 1",
                    (f'%{specialization}%',)
                )
            else:
                cursor = conn.execute("SELECT * FROM masters WHERE is_active = 1")

            return [dict(row) for row in cursor.fetchall()]

    def get_services(self, category: str = None) -> List[Dict]:
        """Получить список услуг"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                cursor = conn.execute(
                    "SELECT * FROM services WHERE category = ?",
                    (category,)
                )
            else:
                cursor = conn.execute("SELECT * FROM services")

            return [dict(row) for row in cursor.fetchall()]

    def check_availability(self, master_id: int, date: str, time: str) -> bool:
        """Проверить доступность мастера"""
        appointment_datetime = f"{date} {time}:00"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE master_id = ? AND appointment_date = ? AND status IN ('booked', 'completed')",
                (master_id, appointment_datetime)
            )

            return cursor.fetchone()[0] == 0

    def create_appointment(self, user_id: int, master_id: int, service_id: int, appointment_datetime: str) -> int:
        """Создать запись"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO appointments (user_id, master_id, service_id, appointment_date) VALUES (?, ?, ?, ?)",
                (user_id, master_id, service_id, appointment_datetime)
            )
            return cursor.lastrowid

    def get_user_appointments(self, user_id: int) -> List[Dict]:
        """Получить записи пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT a.*, m.name as master_name, s.name as service_name, s.price
                FROM appointments a
                JOIN masters m ON a.master_id = m.id
                JOIN services s ON a.service_id = s.id
                WHERE a.user_id = ?
                ORDER BY a.appointment_date DESC
            """, (user_id,))

            return [dict(row) for row in cursor.fetchall()]