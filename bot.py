import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import config
from database import Database
from booking_system import BookingSystem
from ollama_client import OllamaClient
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class BeauteqBot:
    def __init__(self):
        self.db = Database()
        self.booking_system = BookingSystem()
        self.llm = OllamaClient()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        self.db.save_user(user.id, user.username, user.first_name)

        welcome_text = f"""
Привет, {user.first_name}! 👋

Я Анастасия, ваш AI-ассистент салона красоты *Beauteq*!

Я могу помочь вам:
💇‍♀️ *Записаться* к мастеру
📅 *Узнать свободное время*
💄 *Подобрать услугу*
💰 *Узнать цены*
📋 *Посмотреть ваши записи*

Просто напишите, что вас интересует!
        """

        keyboard = [
            [KeyboardButton("📅 Записаться"), KeyboardButton("💇 Услуги и цены")],
            [KeyboardButton("👩‍💼 Наши мастера"), KeyboardButton("📋 Мои записи")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        # Сохраняем в историю
        self.db.save_conversation(user.id, "/start", False, "start")
        self.db.save_conversation(user.id, welcome_text, True, "welcome")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user = update.effective_user
        user_message = update.message.text

        # Сохраняем сообщение пользователя
        self.db.save_user(user.id, user.username, user.first_name)
        self.db.save_conversation(user.id, user_message, False, "message")

        # Показываем индикатор "печатает"
        await update.message.chat.send_action(action="typing")

        try:
            # Определяем тип запроса
            if any(word in user_message.lower() for word in ['записаться', 'запись', 'бронь']):
                # Обработка бронирования
                response = self.booking_system.process_booking_request(
                    user_message, user.id, user.first_name
                )
            else:
                # Общий диалог
                response = self.llm.chat([
                    {"role": "user", "content": user_message}
                ])

            # Отправляем ответ
            if "text" in response:
                await update.message.reply_text(response["text"])
                self.db.save_conversation(user.id, response["text"], True, "response")

            # Обрабатываем результаты функций
            elif response.get("type") == "function_result":
                result = response["result"]

                if response["function"] == "create_appointment":
                    if result.get("success"):
                        appointment_text = f"""
✅ *Запись успешно создана!*

*Мастер:* {result['master']}
*Услуга:* {result['service']}  
*Дата:* {result['date']}
*Время:* {result['time']}
*Стоимость:* {result['price']} руб.

Ждем вас в салоне Beauteq! 🎉
                        """
                        await update.message.reply_text(appointment_text, parse_mode='Markdown')
                        self.db.save_conversation(user.id, appointment_text, True, "appointment_created")
                    else:
                        error_text = f"❌ Не удалось создать запись: {result.get('error', 'Неизвестная ошибка')}"
                        await update.message.reply_text(error_text)
                        self.db.save_conversation(user.id, error_text, True, "appointment_error")

                else:
                    # Для других функций просто показываем результат
                    result_text = json.dumps(result, ensure_ascii=False, indent=2)
                    await update.message.reply_text(f"Результат: {result_text}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_text = "Извините, произошла ошибка. Пожалуйста, попробуйте позже."
            await update.message.reply_text(error_text)
            self.db.save_conversation(user.id, error_text, True, "error")

    async def show_services(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать услуги и цены"""
        # Показываем индикатор загрузки
        await update.message.chat.send_action(action="typing")

        services = self.db.get_services()

        services_text = "💇 *Наши услуги и цены:*\n\n"
        for service in services:
            services_text += f"*{service['name']}* - {service['price']} руб. ({service['duration_minutes']} мин.)\n"

        await update.message.reply_text(services_text, parse_mode='Markdown')

    async def show_masters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать мастеров"""
        # Показываем индикатор загрузки
        await update.message.chat.send_action(action="typing")

        masters = self.db.get_available_masters()

        masters_text = "👩‍💼 *Наши мастера:*\n\n"
        for master in masters:
            masters_text += f"*{master['name']}* - {master['specialization']}\n"

        await update.message.reply_text(masters_text, parse_mode='Markdown')

    async def show_my_appointments(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать записи пользователя"""
        # Показываем индикатор загрузки
        await update.message.chat.send_action(action="typing")

        user = update.effective_user
        appointments = self.db.get_user_appointments(user.id)

        if not appointments:
            await update.message.reply_text("У вас пока нет записей.")
            return

        appointments_text = "📋 *Ваши записи:*\n\n"
        for appt in appointments:
            appointments_text += f"*{appt['master_name']}* - {appt['service_name']}\n"
            appointments_text += f"📅 {appt['appointment_date']}\n"
            appointments_text += f"💵 {appt['price']} руб.\n"
            appointments_text += f"Статус: {appt['status']}\n\n"

        await update.message.reply_text(appointments_text, parse_mode='Markdown')

    async def handle_contacts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать контакты"""
        contacts_text = f"""
📞 *Контакты салона Beauteq*

*Телефон:* {config.SALON_PHONE}
*Режим работы:* {config.WORKING_HOURS}

📍 *Адрес:* г. Москва, ул. Красивая, д. 1

Мы всегда рады вам! 💫
        """
        await update.message.reply_text(contacts_text, parse_mode='Markdown')


def main():
    """Запуск бота"""
    bot = BeauteqBot()

    # Создаем Application
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("services", bot.show_services))
    application.add_handler(CommandHandler("masters", bot.show_masters))
    application.add_handler(CommandHandler("appointments", bot.show_my_appointments))
    application.add_handler(CommandHandler("contacts", bot.handle_contacts))

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # Запускаем бота
    logger.info("Beauteq Bot is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()