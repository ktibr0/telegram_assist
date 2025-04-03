import os
import logging
from dotenv import load_dotenv
from telegram import Update, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DB = os.getenv('MONGODB_DB')

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
messages_collection = db['messages']
blocked_users_collection = db['blocked_users']

async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Я бот-ассистент. Я передам ваше сообщение владельцу. "
        f"Просто напишите ваше сообщение, и я его перешлю.",
        reply_markup=ForceReply(selective=True),
    )
    logger.info(f"Пользователь {user.id} (@{user.username}) запустил бота")
    
    # Всегда отправляем уведомление администратору, независимо от того, кто запустил бота
    try:
        if user.id != ADMIN_USER_ID:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"📢 Новый пользователь запустил бота:\n"
                     f"👤 {user.first_name} {user.last_name or ''} (@{user.username or 'без username'})\n"
                     f"🆔 ID: {user.id}"
            )
            logger.info(f"Отправлено уведомление администратору о новом пользователе {user.id}")
        else:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"✅ Бот запущен вами (администратором)."
            )
            logger.info("Бот запущен администратором")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}")

async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    message = update.message
    logger.info(f"Получено сообщение от пользователя {user.id} (@{user.username})")
    
    if blocked_users_collection.find_one({"user_id": user.id}):
        logger.info(f"Сообщение от заблокированного пользователя {user.id} проигнорировано")
        return
    
    message_data = {
        "user_id": user.id,
        "username": user.username or "Нет имени пользователя",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "message_id": message.message_id,
        "text": message.text or "",
        "caption": message.caption or "",
        "date": datetime.now(),
        "file_id": None,
        "file_type": None
    }
    
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
    
    result = messages_collection.insert_one(message_data)
    message_id_in_db = result.inserted_id
    logger.info(f"Сообщение от пользователя {user.id} сохранено в базе данных с ID: {message_id_in_db}")
    
    user_info = f"👤 Пользователь: {user.first_name} {user.last_name or ''} (@{user.username or 'без username'})\n🆔 ID: {user.id}"
    
    keyboard = [
        [
            InlineKeyboardButton("Заблокировать", callback_data=f"block_{user.id}"),
            InlineKeyboardButton("Ответить", callback_data=f"reply_{user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if file_id:
            if file_type == 'photo':
                await context.bot.send_photo(
                    chat_id=int(ADMIN_USER_ID),
                    photo=file_id,
                    caption=f"{user_info}\n\nПрислал фото" + (f" с текстом: {message.caption}" if message.caption else ""),
                    reply_markup=reply_markup  # Ensure reply buttons are always present
                )
                logger.info(f"Фото от пользователя {user.id} переслано администратору")
            elif file_type == 'document':
                await context.bot.send_document(
                    chat_id=int(ADMIN_USER_ID),
                    document=file_id,
                    caption=f"{user_info}\n\nПрислал документ" + (f" с текстом: {message.caption}" if message.caption else ""),
                    reply_markup=reply_markup  # Ensure reply buttons are always present
                )
                logger.info(f"Документ от пользователя {user.id} переслан администратору")
            elif file_type == 'video':
                await context.bot.send_video(
                    chat_id=int(ADMIN_USER_ID),
                    video=file_id,
                    caption=f"{user_info}\n\nПрислал видео" + (f" с текстом: {message.caption}" if message.caption else ""),
                    reply_markup=reply_markup  # Ensure reply buttons are always present
                )
                logger.info(f"Видео от пользователя {user.id} переслан администратору")
            elif file_type == 'voice':
                await context.bot.send_voice(
                    chat_id=int(ADMIN_USER_ID),
                    voice=file_id,
                    caption=f"{user_info}\n\nПрислал голосовое сообщение",
                    reply_markup=reply_markup  # Ensure reply buttons are always present
                )
                logger.info(f"Голосовое сообщение от пользователя {user.id} переслано администратору")
            elif file_type == 'audio':
                await context.bot.send_audio(
                    chat_id=int(ADMIN_USER_ID),
                    audio=file_id,
                    caption=f"{user_info}\n\nПрислал аудио" + (f" с текстом: {message.caption}" if message.caption else ""),
                    reply_markup=reply_markup  # Ensure reply buttons are always present
                )
                logger.info(f"Аудио от пользователя {user.id} переслано администратору")
            elif file_type == 'sticker':
                # Send message first with reply buttons
                await context.bot.send_message(
                    chat_id=int(ADMIN_USER_ID),
                    text=f"{user_info}\n\nПрислал стикер:",
                    reply_markup=reply_markup  # Ensure reply buttons are always present
                )
                # Then send the sticker separately
                await context.bot.send_sticker(
                    chat_id=int(ADMIN_USER_ID),
                    sticker=file_id
                )
                logger.info(f"Стикер от пользователя {user.id} переслан администратору")
        else:
            sent_message = await context.bot.send_message(
                chat_id=int(ADMIN_USER_ID),
                text=f"{user_info}\n\n📝 Сообщение: {message.text or '[Пустое сообщение]'}",
                reply_markup=reply_markup
            )
            logger.info(f"Текстовое сообщение от пользователя {user.id} переслано администратору, message_id: {sent_message.message_id}")
    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения администратору: {str(e)}")
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_USER_ID),
                text=f"⚠️ Ошибка при пересылке сообщения от пользователя {user.id}:\n{str(e)}"
            )
        except Exception as inner_e:
            logger.critical(f"Критическая ошибка при отправке уведомления о проблеме: {str(inner_e)}")
    
    try:
        await update.message.reply_text("Спасибо! Ваше сообщение было передано.")
        logger.info(f"Подтверждение отправлено пользователю {user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке подтверждения пользователю {user.id}: {str(e)}")

async def get_messages(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        # Проверяем, откуда пришел запрос (из сообщения или из callback query)
        if update.callback_query:
            await update.callback_query.message.reply_text("У вас нет доступа к этой команде.")
        else:
            await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /messages")
        return
    
    args = context.args
    limit = 10 
    if args and args[0].isdigit():
        limit = int(args[0])
    
    latest_messages = list(messages_collection.find().sort("date", -1).limit(limit))
    
    if not latest_messages:
        # Проверяем, откуда пришел запрос
        if update.callback_query:
            await update.callback_query.message.reply_text("Сообщений пока нет.")
        else:
            await update.message.reply_text("Сообщений пока нет.")
        logger.info("Запрос на получение сообщений: сообщений нет")
        return
    
    response = "📬 Последние сообщения:\n\n"
    for idx, msg in enumerate(latest_messages, 1):
        username = msg.get("username", "Нет имени пользователя")
        if username == "Нет имени пользователя":
            username = f"{msg.get('first_name', '')} {msg.get('last_name', '')}"
            if username.strip() == "":
                username = f"ID: {msg['user_id']}"
        
        if msg.get("file_type"):
            text = f"[{msg.get('file_type', 'вложение')}]" + (f" с текстом: {msg.get('caption', '')[:30]}" if msg.get('caption') else "")
        else:
            text = msg.get("text", "") or "[Пустое сообщение]"
        
        response += f"{idx}. 🕒 {msg['date'].strftime('%d.%m.%Y %H:%M')}\n"
        response += f"👤 {username} (ID: {msg['user_id']})\n"
        response += f"📝 {text[:50]}{'...' if len(text) > 50 else ''}\n\n"
    
    # Создаем улучшенное навигационное меню
    keyboard = []
    
    # Добавляем кнопки с номерами сообщений
    message_buttons = []
    for idx, msg in enumerate(latest_messages, 1):
        if len(message_buttons) < 5:  # По 5 кнопок в ряду
            message_buttons.append(InlineKeyboardButton(f"{idx}", callback_data=f"view_msg_{str(msg['_id'])}"))
        else:
            keyboard.append(message_buttons)
            message_buttons = [InlineKeyboardButton(f"{idx}", callback_data=f"view_msg_{str(msg['_id'])}")]
    
    if message_buttons:  # Добавляем последний ряд кнопок
        keyboard.append(message_buttons)
    
    # Добавляем дополнительные функциональные кнопки
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="refresh_messages"),
        InlineKeyboardButton("🔍 Больше сообщений", callback_data=f"more_messages_{limit}")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Проверяем, откуда пришел запрос
    if update.callback_query:
        await update.callback_query.message.reply_text(response, reply_markup=reply_markup)
    else:
        await update.message.reply_text(response, reply_markup=reply_markup)
    
    logger.info(f"Запрос на получение {limit} сообщений выполнен")

async def view_message(update: Update, context: CallbackContext, message_id_str: str) -> None:
    try:
        from bson import ObjectId
        message = messages_collection.find_one({"_id": ObjectId(message_id_str)})
        
        if not message:
            await update.callback_query.message.reply_text("Сообщение не найдено в базе данных.")
            logger.warning(f"Попытка просмотреть несуществующее сообщение с ID {message_id_str}")
            return
        
        username = message.get("username") or f"{message.get('first_name', '')} {message.get('last_name', '')}"
        if username.strip() == "":
            username = f"Пользователь с ID: {message['user_id']}"
        
        detail_text = f"📝 Детали сообщения:\n\n"
        detail_text += f"👤 Пользователь: {username}\n"
        detail_text += f"🆔 ID пользователя: {message['user_id']}\n"
        detail_text += f"🕒 Дата: {message['date'].strftime('%d.%m.%Y %H:%M:%S')}\n"
        
        file_id = message.get("file_id")
        file_type = message.get("file_type")
        
        if file_type:
            detail_text += f"📎 Тип файла: {file_type}\n"
            if message.get("caption"):
                detail_text += f"📄 Подпись: {message['caption']}\n"
        else:
            detail_text += f"📄 Текст: {message['text']}\n"
        
        # Создаем клавиатуру с кнопками действий
        keyboard = [
            [InlineKeyboardButton("✏️ Ответить", callback_data=f"reply_{message['user_id']}")],
            [InlineKeyboardButton("🚫 Заблокировать", callback_data=f"block_{message['user_id']}")],
            [InlineKeyboardButton("⬅️ Вернуться к списку", callback_data="back_to_messages")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        logger.info(f"Отправка деталей сообщения с ID {message_id_str} с кнопками навигации")
        
        # Отправляем сообщение с деталями и кнопками
        message_with_buttons = await update.callback_query.message.reply_text(detail_text, reply_markup=reply_markup)
        
        # Если сообщение содержит медиафайл, отправляем его
        if file_id:
            try:
                if file_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=update.callback_query.message.chat_id,
                        photo=file_id,
                        caption="📷 Фото из сообщения"
                    )
                elif file_type == 'document':
                    await context.bot.send_document(
                        chat_id=update.callback_query.message.chat_id,
                        document=file_id,
                        caption="📄 Документ из сообщения"
                    )
                elif file_type == 'video':
                    await context.bot.send_video(
                        chat_id=update.callback_query.message.chat_id,
                        video=file_id,
                        caption="🎥 Видео из сообщения"
                    )
                elif file_type == 'voice':
                    await context.bot.send_voice(
                        chat_id=update.callback_query.message.chat_id,
                        voice=file_id,
                        caption="🎤 Голосовое сообщение"
                    )
                elif file_type == 'audio':
                    await context.bot.send_audio(
                        chat_id=update.callback_query.message.chat_id,
                        audio=file_id,
                        caption="🎵 Аудио из сообщения"
                    )
                elif file_type == 'sticker':
                    await context.bot.send_sticker(
                        chat_id=update.callback_query.message.chat_id,
                        sticker=file_id
                    )
                logger.info(f"Отправлен медиафайл типа {file_type} для сообщения с ID {message_id_str}")
            except Exception as e:
                logger.error(f"Ошибка при отправке медиафайла: {str(e)}")
                await update.callback_query.message.reply_text(f"Ошибка при отправке медиафайла: {str(e)}")
        
        logger.info(f"Просмотр деталей сообщения с ID {message_id_str} успешно завершен")
    except Exception as e:
        logger.error(f"Ошибка при показе детальной информации о сообщении: {str(e)}")
        await update.callback_query.message.reply_text(f"Произошла ошибка: {str(e)}")

async def block_user(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /block")
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"⚠️ Пользователь с ID {user.id} пытался получить доступ к административной команде /block"
        )
        return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Пожалуйста, укажите ID пользователя. Например: /block 123456789")
        return
    
    user_id = int(args[0])
    
    if not messages_collection.find_one({"user_id": user_id}):
        await update.message.reply_text(f"Пользователь с ID {user_id} не найден в базе данных.")
        logger.warning(f"Попытка заблокировать несуществующего пользователя с ID {user_id}")
        return
    
    if blocked_users_collection.find_one({"user_id": user_id}):
        await update.message.reply_text(f"Пользователь с ID {user_id} уже заблокирован.")
        logger.info(f"Попытка заблокировать уже заблокированного пользователя с ID {user_id}")
        return
    
    blocked_users_collection.insert_one({
        "user_id": user_id,
        "blocked_by": user.id,
        "blocked_at": datetime.now()
    })
    
    await update.message.reply_text(f"Пользователь с ID {user_id} заблокирован.")
    logger.info(f"Пользователь с ID {user_id} заблокирован администратором")

async def unblock_user(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /unblock")
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"⚠️ Пользователь с ID {user.id} пытался получить доступ к административной команде /unblock"
        )
        return
    
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Пожалуйста, укажите ID пользователя. Например: /unblock 123456789")
        return
    
    user_id = int(args[0])
    result = blocked_users_collection.delete_one({"user_id": user_id})
    
    if result.deleted_count > 0:
        await update.message.reply_text(f"Пользователь с ID {user_id} разблокирован.")
        logger.info(f"Пользователь с ID {user_id} разблокирован администратором")
    else:
        await update.message.reply_text(f"Пользователь с ID {user_id} не был заблокирован.")
        logger.warning(f"Попытка разблокировать незаблокированного пользователя с ID {user_id}")

async def get_blocked_users(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /blocked")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"⚠️ Пользователь с ID {user.id} пытался получить доступ к административной команде /blocked"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}")
        return
    
    try:
        blocked_users = list(blocked_users_collection.find())
        
        if not blocked_users:
            await update.message.reply_text("Заблокированных пользователей нет.")
            logger.info("Запрос на получение списка заблокированных пользователей: список пуст")
            return
        
        response = "🚫 Заблокированные пользователи:\n\n"
        
        for i, user_data in enumerate(blocked_users, 1):
            user_info = messages_collection.find_one({"user_id": user_data["user_id"]})
            username = "Неизвестный пользователь"
            
            if user_info:
                if user_info.get("username"):
                    username = f"@{user_info['username']}"
                else:
                    username = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"
                    if username.strip() == "":
                        username = f"ID: {user_data['user_id']}"
            
            blocked_at = user_data["blocked_at"].strftime("%d.%m.%Y %H:%M")
            user_id = user_data["user_id"]
            
            response += f"{i}. 👤 {username}\n"
            response += f"🆔 ID: `{user_id}`\n"  # Используем форматирование Markdown для легкого копирования
            response += f"⏱️ Заблокирован: {blocked_at}\n\n"
        
        # Создаем клавиатуру с ID для разблокировки
        keyboard = []
        row = []
        for i, user_data in enumerate(blocked_users, 1):
            user_id = user_data["user_id"]
            if len(row) < 2:  # По 2 кнопки в ряду
                row.append(InlineKeyboardButton(
                    f"Разблокировать ID: {user_id}",
                    callback_data=f"unblock_{user_id}"
                ))
            else:
                keyboard.append(row)
                row = [InlineKeyboardButton(
                    f"Разблокировать ID: {user_id}",
                    callback_data=f"unblock_{user_id}"
                )]
        
        if row:  # Добавляем последний ряд кнопок
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown")
        logger.info("Запрос на получение списка заблокированных пользователей выполнен")
    except Exception as e:
        logger.error(f"Ошибка при получении списка заблокированных пользователей: {str(e)}")
        await update.message.reply_text(f"Произошла ошибка при получении списка заблокированных пользователей: {str(e)}")

async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    
    logger.info(f"Получен callback запрос: {data}")
    
    if data.startswith("block_"):
        user_id = int(data.split("_")[1])
        
        if blocked_users_collection.find_one({"user_id": user_id}):
            await query.message.reply_text(text=f"Пользователь с ID {user_id} уже заблокирован.")
            logger.info(f"Попытка заблокировать уже заблокированного пользователя с ID {user_id}")
            return
        
        blocked_users_collection.insert_one({
            "user_id": user_id,
            "blocked_by": ADMIN_USER_ID,
            "blocked_at": datetime.now()
        })
        
        # Отправляем новое сообщение вместо редактирования
        await query.message.reply_text(text=f"🚫 Пользователь с ID {user_id} заблокирован.")
        logger.info(f"Пользователь с ID {user_id} заблокирован через кнопку в интерфейсе")
    
    elif data.startswith("unblock_"):
        user_id = int(data.split("_")[1])
        result = blocked_users_collection.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await query.message.reply_text(text=f"✅ Пользователь с ID {user_id} разблокирован.", parse_mode="Markdown")
            logger.info(f"Пользователь с ID {user_id} разблокирован через кнопку в интерфейсе")
        else:
            await query.message.reply_text(text=f"Пользователь с ID {user_id} не был заблокирован.", parse_mode="Markdown")
            logger.warning(f"Попытка разблокировать незаблокированного пользователя с ID {user_id}")
    
    elif data.startswith("reply_"):
        user_id = int(data.split("_")[1])
        context.user_data["reply_to"] = user_id
        
        user_info = messages_collection.find_one({"user_id": user_id})
        username = "Неизвестный пользователь"
        
        if user_info:
            if user_info.get("username"):
                username = f"@{user_info['username']}"
            else:
                username = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}"
                if username.strip() == "":
                    username = f"Пользователь с ID: {user_id}"
        
        # Отправляем новое сообщение вместо редактирования существующего
        await query.message.reply_text(f"✏️ Теперь вы отвечаете пользователю {username} (ID: {user_id}).\nОтправьте ваш ответ или используйте /cancel для отмены.")
        logger.info(f"Активирован режим ответа пользователю с ID {user_id}")
    
    elif data.startswith("view_msg_"):
        message_id_str = data.split("_")[2]
        logger.info(f"Запрос на просмотр сообщения с ID {message_id_str}")
        await view_message(update, context, message_id_str)
        logger.info(f"Просмотр сообщения с ID {message_id_str} завершен")
    
    elif data == "back_to_messages":
        logger.info("Получен запрос на возврат к списку сообщений")
        context.args = []  # По умолчанию запрашиваем стандартное количество сообщений (10)
        await get_messages(update, context)
        logger.info("Возврат к списку сообщений выполнен")
        
    elif data == "refresh_messages":
        # Обновление списка сообщений
        logger.info("Получен запрос на обновление списка сообщений")
        context.args = []  # Сбрасываем аргументы, чтобы получить стандартное количество сообщений
        await get_messages(update, context)
        logger.info("Обновление списка сообщений выполнено")
    
    elif data.startswith("more_messages_"):
        # Получение большего количества сообщений
        try:
            current_limit = int(data.split("_")[2])
            new_limit = current_limit + 10  # Увеличиваем на 10
            logger.info(f"Получен запрос на больше сообщений (новый лимит: {new_limit})")
            context.args = [str(new_limit)]
            await get_messages(update, context)
            logger.info(f"Запрос на больше сообщений выполнен (лимит: {new_limit})")
        except Exception as e:
            logger.error(f"Ошибка при запросе большего количества сообщений: {str(e)}")
            await query.message.reply_text(f"Произошла ошибка: {str(e)}")

async def cancel(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        logger.warning(f"Пользователь {user.id} пытался получить доступ к административной команде /cancel")
        return
    
    if "reply_to" in context.user_data:
        del context.user_data["reply_to"]
        await update.message.reply_text("Режим ответа отменен.")
        logger.info("Режим ответа отменен")
    else:
        await update.message.reply_text("Нет активного режима ответа.")

async def admin_reply(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        return
    
    if "reply_to" not in context.user_data:
        return
    
    user_id = context.user_data["reply_to"]
    message = update.message
    
    try:
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
        
        del context.user_data["reply_to"]
        await update.message.reply_text(f"Сообщение отправлено пользователю (ID: {user_id}).")
        logger.info(f"Ответ отправлен пользователю с ID {user_id}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке сообщения: {str(e)}")
        logger.error(f"Ошибка при отправке ответа пользователю {user_id}: {str(e)}")

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("messages", get_messages))
    application.add_handler(CommandHandler("block", block_user))
    application.add_handler(CommandHandler("unblock", unblock_user))
    application.add_handler(CommandHandler("blocked", get_blocked_users))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.USER & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.User(ADMIN_USER_ID),
        admin_reply
    ))
    
    application.add_handler(MessageHandler(
        filters.USER & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_message
    ))
    
    logger.info("Бот запущен и готов к работе")
    print(f"Бот запущен. ADMIN_USER_ID установлен на {ADMIN_USER_ID}")
    
    application.run_polling()

if __name__ == "__main__":
    main()