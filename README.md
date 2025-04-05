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

물론이죠! 아래는 당신이 원하는 대로 Google Cloud Vision 설정 안내를 **4번과 6번 사이**에 맞게 자연스럽게 삽입한 **수정된 `Setup Instructions`**입니다:

---

## Setup Instructions

1. Clone this repository  
2. Create a `.env` file with the following variables (or copy from `.env.example`):
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_APPLICATION_CREDENTIALS=path_to_google_credentials.json
   MONGODB_URI=your_mongodb_connection_string
   GOOGLE_GEMINI_API_KEY=your_gemini_api_key
   USE_GOOGLE_VISION=True
   USE_GOOGLE_GEMINI=True
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install Tesseract OCR:
   - For macOS: `brew install tesseract`
   - For Ubuntu: `sudo apt install tesseract-ocr`
   - For Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

5. Set up Google Cloud Vision API (if `USE_GOOGLE_VISION=True`):
   - Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
   - Create a project (e.g., `insurance-bot-project`)
   - Enable **Cloud Vision API** under **APIs & Services > Library**
   - Create a **Service Account** under **IAM & Admin > Service Accounts**
     - Assign at least the `Vision AI User` role
     - Generate and download a **JSON key file**
   - Set the path to the key file in your `.env`:
     ```env
     GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your/insurance-bot-key.json
     ```
   - (Optional) You can also set it in your code using:
     ```python
     import os
     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/absolute/path/to/key.json"
     ```
   - Make sure to **exclude the `.json` file from version control**:
     Add this to `.gitignore`:
     ```txt
     *.json
     ```

6. Run the bot:
   ```bash
   python -m app.bot
   ```

## API Configuration

The application can use either OpenAI or Google Gemini for natural language processing tasks:

- **OpenAI**: Set `OPENAI_API_KEY` in your `.env` file
- **Google Gemini**: Set `GOOGLE_GEMINI_API_KEY` and `USE_GOOGLE_GEMINI=True` in your `.env` file

If `OPENAI_API_KEY` is missing and `USE_GOOGLE_GEMINI=True`, the system will automatically use Google Gemini for all NLP tasks. If both API keys are provided, it will use the one specified by `USE_GOOGLE_GEMINI`.

### Google Cloud Authentication

The `GOOGLE_APPLICATION_CREDENTIALS` environment variable points to a service account key file (`insurance-bot-key.json`) that grants access to Google Cloud services:

- When `USE_GOOGLE_VISION=True`, this key authenticates requests to Google Vision API for OCR processing of uploaded documents
- The service account must have the appropriate IAM permissions for Vision API

To obtain your own service account key:
1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Vision API and Gemini API for your project
3. Create a service account with appropriate permissions
4. Download the JSON key file and place it in your project directory
5. Update the `.env` file to point to this key file

## Project Structure

- `