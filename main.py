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
    
    # Логирование запуска бота пользователем
    logger.info(f"Пользователь {user.id} (@{user.username}) запустил бота")
    
    # Уведомление администратора о новом пользователе, если это не сам администратор
    if user.id != ADMIN_USER_ID:
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"📢 Новый пользователь запустил бота:\n"
                 f"👤 {user.first_name} {user.last_name or ''} (@{user.username or 'без username'})\n"
                 f"🆔 ID: {user.id}"
        )


# Обработка сообщений
async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    message = update.message
    
    # Логирование полученного сообщения
    logger.info(f"Получено сообщение от пользователя {user.id} (@{user.username})")
    
    # Проверка, заблокирован ли пользователь
    if blocked_users_collection.find_one({"user_id": user.id}):
        logger.info(f"Сообщение от заблокированного пользователя {user.id} проигнорировано")
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
    elif message.audio:
        file_id = message.audio.file_id
        file_type = 'audio'
    elif message.sticker:
        file_id = message.sticker.file_id
        file_type = 'sticker'
    
    message_data["file_id"] = file_id
    message_data["file_type"] = file_type
    
    # Вставка сообщения в базу данных
    messages_collection.insert_one(message_data)
    logger.info(f"Сообщение от пользователя {user.id} сохранено в базе данных")
    
    # Формирование информации о пользователе
    user_info = f"👤 Пользователь: {user.first_name} {user.last_name or ''} (@{user.username or 'без username'})\n🆔 ID: {user.id}"
    
    try:
        # Пересылка сообщения администратору с явным указанием chat_id
        if file_id:
            if file_type == 'photo':
                await context.bot.send_photo(
                    chat_id=int(ADMIN_USER_ID),  # Явное преобразование в int для уверенности
                    photo=file_id,
                    caption=f"{user_info}\n\nПрислал фото" + (f" с текстом: {message.caption}" if message.caption else "")
                )
                logger.info(f"Фото от пользователя {user.id} переслано администратору")
            
            elif file_type == 'document':
                await context.bot.send_document(
                    chat_id=int(ADMIN_USER_ID),
                    document=file_id,
                    caption=f"{user_info}\n\nПрислал документ" + (f" с текстом: {message.caption}" if message.caption else "")
                )
                logger.info(f"Документ от пользователя {user.id} переслан администратору")
            
            elif file_type == 'video':
                await context.bot.send_video(
                    chat_id=int(ADMIN_USER_ID),
                    video=file_id,
                    caption=f"{user_info}\n\nПрислал видео" + (f" с текстом: {message.caption}" if message.caption else "")
                )
                logger.info(f"Видео от пользователя {user.id} переслано администратору")
            
            elif file_type == 'voice':
                await context.bot.send_voice(
                    chat_id=int(ADMIN_USER_ID),
                    voice=file_id,
                    caption=f"{user_info}\n\nПрислал голосовое сообщение"
                )
                logger.info(f"Голосовое сообщение от пользователя {user.id} переслано администратору")
            
            elif file_type == 'audio':
                await context.bot.send_audio(
                    chat_id=int(ADMIN_USER_ID),
                    audio=file_id,
                    caption=f"{user_info}\n\nПрислал аудио" + (f" с текстом: {message.caption}" if message.caption else "")
                )
                logger.info(f"Аудио от пользователя {user.id} переслано администратору")
            
            elif file_type == 'sticker':
                # Сначала отправляем информацию о пользователе
                await context.bot.send_message(
                    chat_id=int(ADMIN_USER_ID),
                    text=f"{user_info}\n\nПрислал стикер:"
                )
                # Затем отправляем сам стикер
                await context.bot.send_sticker(
                    chat_id=int(ADMIN_USER_ID),
                    sticker=file_id
                )
                logger.info(f"Стикер от пользователя {user.id} переслан администратору")
        else:
            # Создаем инлайн-кнопки для взаимодействия
            keyboard = [
                [
                    InlineKeyboardButton("Заблокировать", callback_data=f"block_{user.id}"),
                    InlineKeyboardButton("Ответить", callback_data=f"reply_{user.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем текстовое сообщение
            sent_message = await context.bot.send_message(
                chat_id=int(ADMIN_USER_ID),
                text=f"{user_info}\n\n📝 Сообщение: {message.text or '[Пустое сообщение]'}",
                reply_markup=reply_markup
            )
            logger.info(f"Текстовое сообщение от пользователя {user.id} переслано администратору, message_id: {sent_message.message_id}")
    
    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения администратору: {str(e)}")
        # Пробуем отправить уведомление о проблеме
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_USER_ID),
                text=f"⚠️ Ошибка при пересылке сообщения от пользователя {user.id}:\n{str(e)}"
            )
        except Exception as inner_e:
            logger.critical(f"Критическая ошибка при отправке уведомления о проблеме: {str(inner_e)}")
    
    # Отправка подтверждения пользователю
    try:
        await update.message.reply_text("Спасибо! Ваше сообщение было передано.")
        logger.info(f"Подтверждение отправлено пользователю {user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке подтверждения пользователю {user.id}: {str(e)}")


# Команда для админа - получить список сообщений
async def get_messages(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /messages")
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
        logger.info("Запрос на получение сообщений: сообщений нет")
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
    logger.info(f"Запрос на получение {limit} сообщений выполнен")


# Команда для админа - заблокировать пользователя
async def block_user(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /block")
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
    logger.info(f"Пользователь с ID {user_id} заблокирован администратором")


# Команда для админа - разблокировать пользователя
async def unblock_user(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /unblock")
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
        logger.info(f"Пользователь с ID {user_id} разблокирован администратором")
    else:
        await update.message.reply_text(f"Пользователь с ID {user_id} не был заблокирован.")


# Команда для админа - получить список заблокированных пользователей
async def get_blocked_users(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /blocked")
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
    logger.info("Запрос на получение списка заблокированных пользователей выполнен")


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
        logger.info(f"Пользователь с ID {user_id} заблокирован через кнопку в интерфейсе")
    
    # Обработка разблокировки пользователя
    elif data.startswith("unblock_"):
        user_id = int(data.split("_")[1])
        
        # Разблокировка пользователя
        result = blocked_users_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await query.edit_message_text(text=f"Пользователь с ID {user_id} разблокирован.")
            logger.info(f"Пользователь с ID {user_id} разблокирован через кнопку в интерфейсе")
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
        logger.info(f"Активирован режим ответа пользователю с ID {user_id}")


# Отмена режима ответа
async def cancel(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    # Проверка, является ли пользователь администратором
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /cancel")
        return
    
    # Очистка контекста
    if "reply_to" in context.user_data:
        del context.user_data["reply_to"]
        await update.message.reply_text("Режим ответа отменен.")
        logger.info("Режим ответа отменен")
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
        elif message.audio:
            await context.bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=message.caption or "Ответ от администратора"
            )
        elif message.sticker:
            await context.bot.send_sticker(
                chat_id=user_id,
                sticker=message.sticker.file_id
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
        logger.info(f"Ответ отправлен пользователю с ID {user_id}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке сообщения: {str(e)}")
        logger.error(f"Ошибка при отправке ответа пользователю {user_id}: {str(e)}")


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
    
    # Запуск бота с выводом информации о начале работы
    logger.info("Бот запущен и готов к работе")
    print(f"Бот запущен. ADMIN_USER_ID установлен на {ADMIN_USER_ID}")
    application.run_polling()


if __name__ == "__main__":
    main()