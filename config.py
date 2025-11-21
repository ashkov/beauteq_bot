import os
from typing import Optional


class Config:
    # Telegram Bot Token
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Ollama Configuration - теперь подключается к хосту
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma2:9b")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///beauteq.db")

    # Salon Information
    SALON_NAME: str = "Beauteq"
    SALON_PHONE: str = "+7 (999) 123-45-67"
    WORKING_HOURS: str = "Пн-Пт: 9:00-21:00, Сб-Вс: 10:00-20:00"

    # System Prompts
    SYSTEM_PROMPT: str = """
Ты - Анастасия, AI-ассистент салона красоты "Beauteq".
Твои характеристики:
- Вежливая, профессиональная, дружелюбная
- Говоришь на "ты" с клиентами
- Всегда уточняешь детали, если информации недостаточно
- Предлагаешь альтернативы, если нужное время/услуга недоступны
- Краткая, но информативная

Правила салона:
- Отмена бесплатна за 24 часа до визита
- Оплата наличными или картой
- Приходите за 10 минут до записи
- При первом посечении заполняется анкета гостя

Всегда представляйся: "Я Анастасия, ваш ассистент Beauteq"
"""


config = Config()