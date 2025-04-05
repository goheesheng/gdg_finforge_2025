# Insurance Claim Assistant Bot

A smart Telegram bot that helps users understand and file insurance claims.

## Features

1. **Policy Upload & AI Understanding**
   - Upload insurance policies as PDF or images
   - Extract policy details using OCR and NLP
   - Store structured policy data

2. **Smart Q&A Chat Assistant**
   - Ask questions about your policies
   - Get answers based on your specific coverage

3. **Claim Recommendation Engine**
   - Enter symptoms or situations
   - Get recommendations on applicable claims

4. **Claim Tracking System**
   - Log and track claims
   - Monitor claim statuses

5. **Multi-Policy Optimizer**
   - Upload multiple policies
   - Get suggestions on optimal claim paths

6. **Automated Claim Form Filling**
   - Auto-generate filled claim forms
   - Download or receive via email

## Setup Instructions

1. Clone this repository
2. Create a `.env` file with the following variables:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_APPLICATION_CREDENTIALS=path_to_google_credentials.json
   MONGODB_URI=your_mongodb_connection_string
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Install Tesseract OCR:
   - For macOS: `brew install tesseract`
   - For Ubuntu: `sudo apt install tesseract-ocr`
   - For Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

5. Run the bot:
   ```
   python app/bot.py
   ```

## Project Structure

- `app/bot.py` - Main bot entry point
- `app/services/` - Core service modules (OCR, NLP, claims)
- `app/database/` - Database connection and models
- `app/utils/` - Utility functions
- `app/config/` - Configuration settings
