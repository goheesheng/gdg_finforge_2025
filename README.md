# Insurance Claim Assistant Bot

#### Reflection
This is our first ever physical hackathon at Nanyang Technological University, there were 50 teams and we made it to the top 6,! Looking back, I think one of the key reasons was that we focused our POC on health insurance. We should’ve highlighted to the judges that our bot isn’t limited to just health—it can easily be applied to other types like financial and general insurance as well.

We learned a lot throughout the hackathon. Interestingly, we initially started by building a crypto bot for cross-border transfers. After several hours of development, we realized it didn’t align closely with our sponsor, Singlife, and was advised who’s more focused on financial insurance. That led us to pivot and create this Insurance Bot instead.

We’ve since upgraded the bot and added new features! The demo video doesn’t show everything yet, but feel free to check out the GitHub repo and try it out.

🔹 Demo Video: https://youtu.be/OTEfyOIROHo

🔹 Physical Pitch Video: https://youtu.be/yi-GO5rMQU4

🔹 GitHub Repo: https://github.com/goheesheng/gdg_finforge_2025 

* *TLDR* A smart Telegram bot that helps users understand and file insurance claims.We pivoted from leveraging AI to onboard beginner users on crypto products, we destroyed the old branch main. this is the pivoted product.**

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
   - (Optional) Set it in code using:
     ```python
     import os
     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/absolute/path/to/key.json"
     ```
   - Make sure to **exclude the `.json` file** in `.gitignore`:
     ```txt
     *.json
     ```

6. Set up MongoDB  
You have two main options:

---

### ✅ Option 1: MongoDB Atlas (Cloud, Recommended)

1. Sign up at [https://www.mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)  
2. Create a **Free Tier Cluster** (e.g., M0 Sandbox)  
3. Go to **Database Access** → Add a user (e.g., `admin`, choose a strong password)  
4. Under **Network Access**, allow access from `0.0.0.0/0` (or your own IP for better security)  
5. Copy your connection URI:  
   `mongodb+srv://admin:yourpassword@cluster0.mongodb.net/?retryWrites=true&w=majority`  
6. Add it to your `.env` file like so:
   ```env
   MONGODB_URI=mongodb+srv://admin:yourpassword@cluster0.mongodb.net/?retryWrites=true&w=majority
   ```

---

### ✅ Option 2: Install MongoDB Locally

#### 🧑‍💻 macOS
```bash
brew tap mongodb/brew
brew install mongodb-community@7.0
brew services start mongodb-community@7.0
```

#### 🧑‍💻 Ubuntu
```bash
sudo apt update
sudo apt install -y mongodb
sudo systemctl start mongodb
sudo systemctl enable mongodb
```

#### 🧑‍💻 Windows
1. Download from [official MongoDB website](https://www.mongodb.com/try/download/community)  
2. Follow the installation wizard  
3. (Optional) Install **MongoDB Compass** GUI

---

### ✅ Test MongoDB connection in Python

1. Install `pymongo`:
   ```bash
   pip install pymongo
   ```

2. Sample test script:
   ```python
   from pymongo import MongoClient
   import os
   from dotenv import load_dotenv

   load_dotenv()
   uri = os.getenv("MONGODB_URI")

   client = MongoClient(uri)
   db = client['insurance_bot']
   collection = db['policies']

   collection.insert_one({"user_id": 12345, "policy_name": "Health Insurance"})

   for doc in collection.find():
       print(doc)
   ```

---

### 🔐 Security Notes

- Never commit your `.env` or credentials files
- Add to `.gitignore`:
  ```txt
  .env
  *.json
  ```
- For production Atlas setups, use specific IP whitelisting and role-based access control

---

7. Run the bot:
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
```
.
├── app/                      # Main application directory
│   ├── bot.py               # Main bot logic
│   ├── services/            # Service layer
│   ├── utils/               # Utility functions
│   ├── database/            # Database related code
│   ├── config/              # Configuration files
│   ├── controllers/         # Controllers
│   └── .env                 # Environment variables
│
├── generated_forms/         # Directory for generated forms
├── temp_downloads/          # Temporary download storage
├── requirements.txt         # Python package dependencies
└── README.md               # Project documentation
```
