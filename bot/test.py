import os
import google.generativeai as genai
from google.generativeai import GenerativeModel

# Configure API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize model
model = GenerativeModel("gemini-1.5-flash")

# Generate content
response = model.generate_content("What is an LLM?")
print(response.text)
