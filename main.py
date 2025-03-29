import os
import logging
from dotenv import load_dotenv
from telegram import Update, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DB = os.getenv('MONGODB_DB')

# Подключение к MongoDB
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
messages_collection = db['messages']
blocked_users_collection = db['blocked_users']


# Команда /start
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Я бот-ассистент. Я передам ваше сообщение владельцу. "
        f"Просто напишите ваше сообщение, и я его перешлю.",
        reply_markup=ForceReply(selective=True),
    )


# Обработка сообщений
async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    message = update.message
    
    # Проверка, заблокирован ли пользователь
    if blocked_users_collection.find_one({"user_id": user.id}):
        return
    
    # Сохранение сообщения в базе данных
    message_data = {
        "user_id": user.id,
        "username": user.username or "Нет имени пользователя",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "message_id": message.message_id,
        "text": message.text or "",
        "date": datetime.now(),
        "file_id": None,
        "file_type": None
    }
    
    # Обработка различных типов сообщений
    file_id = None
    file_type = None
    
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = 'photo'
    elif message.document:
        file_id = message.document.file_id
        file_type = 'document'
    elif message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.voice:
        file_id = message.voice.file_id
        file_type = 'voice'
    
    message_data["file_id"] = file_id
    message_data["file_type"] = file_type
    
    messages_collection.insert_one(message_data)
    
    # Отправка сообщения администратору
    user_info = f"👤 Пользователь: {user.first_name} {user.last_name or ''} (@{user.username or 'без username'})\n🆔 ID: {user.id}"
    
    # Пересылка сообщения администратору
    if file_id:
        if file_type == 'photo':
            await context.bot.send_photo(
                chat_id=ADMIN_USER_ID,
                photo=file_id,
                caption=f"{user_info}\n\nПрислал фото" + (f" с текстом: {message.caption}" if message.caption else "")
            )
        elif file_type == 'document':
            await context.bot.send_document(
                chat_id=ADMIN_USER_ID,
                document=file_id,
                caption=f"{user_info}\n\nПрислал документ" + (f" с текстом: {message.caption}" if message.caption else "")
            )
        elif file_type == 'video':
            await context.bot.send_video(
                chat_id=ADMIN_USER_ID,
                video=file_id,
                caption=f"{user_info}\n\nПрислал видео" + (f" с текстом: {message.caption}" if message.caption else "")
            )
        elif file_type == 'voice':
            await context.bot.send_voice(
                chat_id=ADMIN_USER_ID,
                voice=file_id,
                caption=f"{user_info}\n\nПрислал голосовое сообщение"
            )
    else:
        keyboard = [
            [
                InlineKeyboardButton("Заблокировать", callback_data=f"block_{user.id}"),
                InlineKeyboardButton("Ответить", callback_data=f"reply_{user.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"{user_info}\n\n📝 Сообщение: {message.text}",
            reply_markup=reply_markup
        )
    
    # Отправка подтверждения пользователю
    await update.message.reply_text("Спасибо! Ваше сообщение было передано.")


# Команда для админа - получить список сообщений
async def get_messages(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    # Парсинг аргументов команды
    args = context.args
    limit = 10  # По умолчанию ограничение 10 сообщений
    
    if args and args[0].isdigit():
        limit = int(args[0])
    
    # Получение последних сообщений из базы данных
    latest_messages = list(messages_collection.find().sort("date", -1).limit(limit))
    
    if not latest_messages:
        await update.message.reply_text("Сообщений пока нет.")
        return
    
    # Формирование и отправка ответа
    response = "📬 Последние сообщения:\n\n"
    for msg in latest_messages:
        username = msg.get("username") or f"{msg.get('first_name', '')} {msg.get('last_name', '')}"
        text = msg.get("text") or f"[{msg.get('file_type', 'вложение')}]"
        response += f"🕒 {msg['date'].strftime('%d.%m.%Y %H:%M')}\n"
        response += f"👤 {username} (ID: {msg['user_id']})\n"
        response += f"📝 {text[:50]}{'...' if len(text) > 50 else ''}\n\n"
    
    await update.message.reply_text(response)


# Команда для админа - заблокировать пользователя
async def block_user(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    # Парсинг аргументов команды
    args = context.args
    
    if not args or not args[0].isdigit():
        await update.message.reply_text("Пожалуйста, укажите ID пользователя. Например: /block 123456789")
        return
    
    user_id = int(args[0])
    
    # Проверка, существует ли пользователь в базе сообщений
    if not messages_collection.find_one({"user_id": user_id}):
        await update.message.reply_text(f"Пользователь с ID {user_id} не найден в базе данных.")
        return
    
    # Проверка, не заблокирован ли пользователь уже
    if blocked_users_collection.find_one({"user_id": user_id}):
        await update.message.reply_text(f"Пользователь с ID {user_id} уже заблокирован.")
        return
    
    # Блокировка пользователя
    blocked_users_collection.insert_one({
        "user_id": user_id,
        "blocked_by": user.id,
        "blocked_at": datetime.now()
    })
    
    await update.message.reply_text(f"Пользователь с ID {user_id} заблокирован.")


# Команда для админа - разблокировать пользователя
async def unblock_user(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    # Парсинг аргументов команды
    args = context.args
    
    if not args or not args[0].isdigit():
        await update.message.reply_text("Пожалуйста, укажите ID пользователя. Например: /unblock 123456789")
        return
    
    user_id = int(args[0])
    
    # Разблокировка пользователя
    result = blocked_users_collection.delete_one({"user_id": user_id})
    
    if result.deleted_count > 0:
        await update.message.reply_text(f"Пользователь с ID {user_id} разблокирован.")
    else:
        await update.message.reply_text(f"Пользователь с ID {user_id} не был заблокирован.")


# Команда для админа - получить список заблокированных пользователей
async def get_blocked_users(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    # Получение списка заблокированных пользователей
    blocked_users = list(blocked_users_collection.find())
    
    if not blocked_users:
        await update.message.reply_text("Заблокированных пользователей нет.")
        return
    
    # Формирование и отправка ответа
    response = "🚫 Заблокированные пользователи:\n\n"
    for user_data in blocked_users:
        # Получение информации о пользователе из коллекции сообщений
        user_info = messages_collection.find_one({"user_id": user_data["user_id"]})
        username = "Неизвестный пользователь"
        
        if user_info:
            if user_info.get("username"):
                username = f"@{user_info['username']}"
            else:
                username = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"
        
        blocked_at = user_data["blocked_at"].strftime("%d.%m.%Y %H:%M")
        response += f"👤 {username}\n"
        response += f"🆔 ID: {user_data['user_id']}\n"
        response += f"⏱️ Заблокирован: {blocked_at}\n\n"
    
    keyboard = []
    for user_data in blocked_users:
        keyboard.append([InlineKeyboardButton(
            f"Разблокировать {user_data['user_id']}", 
            callback_data=f"unblock_{user_data['user_id']}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(response, reply_markup=reply_markup)


# Обработка callback-запросов от инлайн-кнопок
async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    # Получение данных из callback_data
    data = query.data
    
    # Обработка блокировки пользователя
    if data.startswith("block_"):
        user_id = int(data.split("_")[1])
        
        # Проверка, не заблокирован ли пользователь уже
        if blocked_users_collection.find_one({"user_id": user_id}):
            await query.edit_message_text(text=f"Пользователь с ID {user_id} уже заблокирован.")
            return
        
        # Блокировка пользователя
        blocked_users_collection.insert_one({
            "user_id": user_id,
            "blocked_by": ADMIN_USER_ID,
            "blocked_at": datetime.now()
        })
        
        await query.edit_message_text(text=f"Пользователь с ID {user_id} заблокирован.")
    
    # Обработка разблокировки пользователя
    elif data.startswith("unblock_"):
        user_id = int(data.split("_")[1])
        
        # Разблокировка пользователя
        result = blocked_users_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await query.edit_message_text(text=f"Пользователь с ID {user_id} разблокирован.")
        else:
            await query.edit_message_text(text=f"Пользователь с ID {user_id} не был заблокирован.")
    
    # Обработка режима ответа пользователю
    elif data.startswith("reply_"):
        user_id = int(data.split("_")[1])
        
        # Сохранение ID пользователя в контексте для последующего ответа
        context.user_data["reply_to"] = user_id
        
        # Получение информации о пользователе
        user_info = messages_collection.find_one({"user_id": user_id})
        username = "Неизвестный пользователь"
        
        if user_info:
            if user_info.get("username"):
                username = f"@{user_info['username']}"
            else:
                username = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"
        
        await query.edit_message_text(
            text=f"Теперь вы отвечаете пользователю {username} (ID: {user_id}).\n"
                 f"Отправьте ваш ответ или используйте /cancel для отмены."
        )


# Отмена режима ответа
async def cancel(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    
    # Очистка контекста
    if "reply_to" in context.user_data:
        del context.user_data["reply_to"]
        await update.message.reply_text("Режим ответа отменен.")
    else:
        await update.message.reply_text("Нет активного режима ответа.")


# Отправка ответа от администратора пользователю
async def admin_reply(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        return
    
    # Проверка, находится ли админ в режиме ответа
    if "reply_to" not in context.user_data:
        return
    
    user_id = context.user_data["reply_to"]
    message = update.message
    
    try:
        # Отправка сообщения пользователю
        if message.photo:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=message.caption or "Ответ от администратора"
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=message.caption or "Ответ от администратора"
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=message.caption or "Ответ от администратора"
            )
        elif message.voice:
            await context.bot.send_voice(
                chat_id=user_id,
                voice=message.voice.file_id,
                caption="Ответ от администратора"
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Ответ от администратора: {message.text}"
            )
        
        # Очистка контекста после отправки ответа
        del context.user_data["reply_to"]
        
        # Подтверждение отправки
        await update.message.reply_text(f"Сообщение отправлено пользователю (ID: {user_id}).")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке сообщения: {str(e)}")


def main() -> None:
    # Создание приложения и добавление обработчиков
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("messages", get_messages))
    application.add_handler(CommandHandler("block", block_user))
    application.add_handler(CommandHandler("unblock", unblock_user))
    application.add_handler(CommandHandler("blocked", get_blocked_users))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Обработчики inline кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик сообщений от админа (для ответа пользователю)
    application.add_handler(MessageHandler(
        filters.USER & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.User(ADMIN_USER_ID),
        admin_reply
    ))
    
    # Обработчик всех других сообщений
    application.add_handler(MessageHandler(
        filters.USER & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_message
    ))
    
    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    main()