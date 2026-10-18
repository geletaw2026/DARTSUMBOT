# DART Engineering Exec Brief Bot

A 24/7 Telegram bot built for DART Engineering Trading OMPLC. It analyzes uploaded construction site documentation, PDFs, and images using Gemini 3.8 Flash to generate concise executive summaries.

## Features
- Executive summarization of engineering and construction documents
- Command handling (`/start`, `/help`)
- Automated analysis of scanned photos and site reports

## Tech Stack
- Python 3
- `pyTelegramBotAPI`
- `google-genai`
- Cloud Hosted on Render

## Environment Variables Required
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather
- `GEMINI_API_KEY`: API key for Gemini models