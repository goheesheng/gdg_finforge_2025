import os
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
from google.generativeai import GenerativeModel


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
import json
import re

class NLPProcessor:
    def __init__(self):
        self.model = GenerativeModel('gemini-1.5-flash-001')
    


    def parse_command(self, text: str) -> dict:
        try:
            # Extract Ethereum address if present using regex
            import re
            eth_address_pattern = r'0x[a-fA-F0-9]{40}'
            address_match = re.search(eth_address_pattern, text)
            
            response = self.model.generate_content(f"""
                Convert this to JSON format identifying:
                - action: swap/stake/etc
                - amount: float
                - from_token: symbol
                - to_token: symbol
                
                User: "{text}"
                Example output:
                {{"action":"swap","amount":100,"from_token":"USDC","to_token":"ETH"}}
                
                IMPORTANT: Return ONLY the JSON object without any backticks, markdown formatting, or explanations.
            """)
            
            # Clean response and parse JSON
            clean_response = response.text
            if clean_response.startswith("```"):
                import re
                clean_response = re.sub(r'^```(?:json)?\s*|\s*```')
            
            result = json.loads(clean_response)
            
            # Add address to result if found
            if address_match:
                result['from_address'] = address_match.group(0)
                
            return result
        except Exception as e:
            print(f"Error parsing command: {str(e)}")
            return {"action": "unknown", "error": str(e)}


