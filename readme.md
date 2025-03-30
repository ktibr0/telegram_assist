# Telegram Bot Proxy

A Telegram bot that acts as a proxy between users and admin, allowing the admin to receive and respond to messages without sharing their direct contact information.
Русская версия 

https://github.com/ktibr0/telegram_assist/blob/main/readme-ru.md


## 📑 Features

- Forwards all user messages to the admin
- Supports various message types (text, photos, documents, videos, voice messages, audio, stickers)
- Admin can reply to users through the bot
- User blocking/unblocking functionality
- Message history tracking
- MongoDB integration for data persistence
- Containerized with Docker for easy deployment

## 🛠️ Tech Stack

- Python 3.10
- python-telegram-bot
- MongoDB
- Docker

## 📋 Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- MongoDB instance (local or cloud-based)

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/telegram-bot-proxy.git
cd telegram-bot-proxy
```

### 2. Set up environment variables

Copy the example environment file and fill in your details:

```bash
cp example.env .env
```

Edit the `.env` file with your information:

```
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ADMIN_USER_ID=your_telegram_user_id

# MongoDB Configuration
MONGODB_URI=mongodb://user:pass@your_mongodb_host:27017/
MONGODB_DB=telegram_bot_db

# MongoDB Credentials
MONGO_USERNAME=user
MONGO_PASSWORD=pass
```

> ⚠️ **Important:** Make sure to set your correct Telegram User ID as the `ADMIN_USER_ID`. This account will receive all messages and have admin privileges.

### 3. Run with Docker Compose

```bash
docker-compose up -d
```

This will build the Docker image and start the container in detached mode.

## 💬 Bot Usage

### For Users

- Start the bot: `/start`
- Send any message (text, photo, document, etc.) to the bot
- The bot will forward your message to the admin and notify you when it's delivered

### For Admin

- View recent messages: `/messages [number]` (default: 10)
- Block a user: `/block user_id`
- Unblock a user: `/unblock user_id`
- View blocked users: `/blocked`
- Reply to a user: Click the "Reply" button on a forwarded message, then send your response
- Cancel reply mode: `/cancel`

## 🚢 Deployment

The project is already set up for deployment using Docker. You can deploy it to any server that supports Docker:

1. Clone the repository on your server
2. Configure the `.env` file
3. Run `docker-compose up -d`
4. Check logs with `docker-compose logs -f`

## 📁 Project Structure

```
└── ./
    ├── docker-compose.yaml  # Docker Compose configuration
    ├── Dockerfile           # Docker image configuration
    ├── example.env          # Example environment variables
    ├── main.py              # Main bot code
    └── requirements.txt     # Python dependencies
```

## 🛡️ Privacy & Security

This bot is designed to protect the admin's privacy by:
- Not revealing the admin's Telegram contact information
- Providing blocking capabilities for unwanted messages
- Storing messages in a secure MongoDB database

## ⚙️ Customization

You can customize the bot's behavior by modifying the `main.py` file:

- Change welcome messages
- Adjust logging behavior
- Add new commands or features
- Modify how messages are displayed

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

## 📄 License

[MIT License](LICENSE)
