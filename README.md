# 🎬 Amazon Movie Bot

A Telegram bot that scrapes new movie releases from Amazon Prime India and sends updates to a Telegram channel, including audio language information.

---

## 🚀 Features

- Scrapes latest movies from Amazon Prime India.
- Extracts movie titles, release year, Prime Video URL, and audio languages.
- Sends formatted updates to a Telegram channel.
- Runs continuously using Railway + UptimeRobot.

---

## 🛠 Tech Stack

- Python 3
- `requests`, `beautifulsoup4`, `python-telegram-bot`
- Hosted on [Railway](https://railway.app)

---

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/amazon-movie-bot.git
   cd amazon-movie-bot
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
3. Set environment variables (optional if hardcoded):
   - TELEGRAM_BOT_TOKEN
   - CHANNEL_ID
4. Run the bot:
   ```bash
   python bot.py


