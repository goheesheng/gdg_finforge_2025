import json
import logging
from typing import Dict, List, Optional, Any, Union
import openai
import os

from app.config.config import (
    OPENAI_API_KEY, 
    USE_GOOGLE_GEMINI, 
    GOOGLE_GEMINI_API_KEY
)
from bson import ObjectId
from datetime import datetime

def convert_mongo_types(obj):
    if isinstance(obj, dict):
        return {k: convert_mongo_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_mongo_types(i) for i in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


logger = logging.getLogger(__name__)

# # Initialize OpenAI
# if OPENAI_API_KEY:
#     openai.api_key = OPENAI_API_KEY

# Configure logging for pdfminer to suppress warnings about CropBox
logging.getLogger("pdfminer.pdfpage").setLevel(logging.ERROR)

# Initialize Google Gemini if enabled
if USE_GOOGLE_GEMINI and GOOGLE_GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
        # Use a different model name that's available in the API
        # gemini-1.5-pro or gemini-1.0-pro are common model names
        try:
            gemini_model = genai.GenerativeModel('gemini-1.5-pro')
            logger.info("Using default model: gemini-1.5-pro")
        except Exception as model_error:
            # If listing fails, try a hardcoded model name
            logger.warning(f"Could not list models: {model_error}. Trying hardcoded model name.")
            gemini_model = genai.GenerativeModel('gemini-1.5-pro')
            logger.info("Using default model: gemini-1.5-pro")
    except ImportError:
        logger.warning("Google Gemini library not available. Falling back to OpenAI.")
        USE_GOOGLE_GEMINI = False
    except Exception as e:
        logger.error(f"Failed to initialize Google Gemini: {e}")
        USE_GOOGLE_GEMINI = False

async def extract_policy_details_openai(policy_text: str) -> Dict:
    """Extract policy details using OpenAI GPT"""
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not provided")
        return {}

    try:
        prompt = f"""
        Extract the key information from this insurance policy:
        
        {policy_text[:10000]}  # Limit text to avoid token limits
        
        Please extract and organize the following information in a structured JSON format:
        
        1. Policy provider/company name
        2. Policy ID/number if available
        3. Policy holder name if available
        4. Coverage period (start and end dates)
        5. Premium amount
        6. Coverage areas and limits (e.g., hospital, dental, vision) with their respective coverage limits
        7. Exclusions (what's not covered)
        8. Deductibles
        9. Copayments or coinsurance details
        10. Out-of-pocket maximums
        11. Special conditions or riders
        
        Output must be valid JSON.
        """
        openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts insurance policy details."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        content = response.choices[0].message.content

        print(content)
        
        # Extract JSON from the response
        try:
            # Find JSON content (it might be wrapped in ```json ... ``` blocks)
            json_content = content
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_content = content.split("```")[1].strip()
                
            return json.loads(json_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from OpenAI response")
            return {"raw_extraction": content}
            
    except Exception as e:
        logger.error(f"Error extracting policy details with OpenAI: {e}")
        return {}

async def extract_policy_details_gemini(policy_text: str) -> Dict:
    """Extract policy details using Google Gemini"""
    if not USE_GOOGLE_GEMINI or not GOOGLE_GEMINI_API_KEY:
        return await extract_policy_details_openai(policy_text)

    try:
        prompt = f"""
        Extract the key information from this insurance policy:
        
        {policy_text[:10000]}  # Limit text to avoid token limits
        
        Please extract and organize the following information in a structured JSON format:
        
        1. Policy provider/company name
        2. Policy ID/number if available
        3. Policy holder name if available
        4. Coverage period (start and end dates)
        5. Premium amount
        6. Coverage areas and limits (e.g., hospital, dental, vision) with their respective coverage limits
        7. Exclusions (what's not covered)
        8. Deductibles
        9. Copayments or coinsurance details
        10. Out-of-pocket maximums
        11. Special conditions or riders
        
        Output must be valid JSON without any other text.
        """
        
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1500,
        }
        
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        content = response.text
        
        try:
            # Find JSON content (it might be wrapped in ```json ... ``` blocks)
            json_content = content
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_content = content.split("```")[1].strip()
                
            return json.loads(json_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from Gemini response")
            return {"raw_extraction": content}
            
    except Exception as e:
        logger.error(f"Error extracting policy details with Gemini: {e}")
        # Fall back to OpenAI
        return await extract_policy_details_openai(policy_text)

async def extract_policy_details(policy_text: str) -> Dict:
    """Extract policy details using the preferred NLP method"""
    if USE_GOOGLE_GEMINI and GOOGLE_GEMINI_API_KEY:
        return await extract_policy_details_gemini(policy_text)
    else:
        return await extract_policy_details_openai(policy_text)

async def answer_question_about_policy_openai(policy_details: Dict, user_question: str) -> str:
    """Answer a question about a policy using OpenAI GPT"""
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not provided")
        return "I'm sorry, I cannot answer questions about your policy right now due to configuration issues."

    try:
        openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        safe_policy = convert_mongo_types(policy_details)
        policy_json = json.dumps(safe_policy, indent=2)
        
        prompt = f"""
        Here is an insurance policy in JSON format:
        
        {policy_json}
        
        The user is asking: "{user_question}"
        
        Please provide a clear, accurate, and concise answer based only on the information in the policy. 
        If the policy doesn't contain information to answer the question, please say so clearly.
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful insurance claims assistant providing accurate information based only on the provided policy details."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        return response.choices[0].message.content
            
    except Exception as e:
        logger.error(f"Error answering question with OpenAI: {e}")
        return "I'm sorry, I encountered an error while processing your question."

async def answer_question_about_policy_gemini(policy_details: Dict, user_question: str) -> str:
    """Answer a question about a policy using Google Gemini"""
    if not USE_GOOGLE_GEMINI or not GOOGLE_GEMINI_API_KEY:
        return await answer_question_about_policy_openai(policy_details, user_question)

    try:
        safe_policy = convert_mongo_types(policy_details)
        policy_json = json.dumps(safe_policy, indent=2)
        
        prompt = f"""
        Here is an insurance policy in JSON format:
        
        {policy_json}
        
        The user is asking: "{user_question}"
        
        Please provide a clear, accurate, and concise answer based only on the information in the policy. 
        If the policy doesn't contain information to answer the question, please say so clearly.
        """
        
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 500,
        }
        
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        return response.text
            
    except Exception as e:
        logger.error(f"Error answering question with Gemini: {e}")
        # Fall back to OpenAI
        return await answer_question_about_policy_openai(policy_details, user_question)

async def answer_question_about_policy(policy_details: Dict, user_question: str) -> str:
    """Answer a question about a policy using the preferred NLP method"""
    if USE_GOOGLE_GEMINI and GOOGLE_GEMINI_API_KEY:
        return await answer_question_about_policy_gemini(policy_details, user_question)
    else:
        return await answer_question_about_policy_openai(policy_details, user_question)

async def recommend_claim_options(policies: List[Dict], situation: str) -> Dict:
    """Recommend claim options based on user's situation"""
    if not policies:
        return {"recommendations": [], "message": "No policies available to analyze."}
        
    # Use the default AI model for recommendations
    if USE_GOOGLE_GEMINI and GOOGLE_GEMINI_API_KEY:
        return await recommend_claim_options_gemini(policies, situation)
    else:
        return await recommend_claim_options_openai(policies, situation)

async def recommend_claim_options_openai(policies: List[Dict], situation: str) -> Dict:
    """Recommend claim options using OpenAI GPT"""
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not provided")
        return {"recommendations": [], "message": "Unable to provide recommendations due to configuration issues."}

    try:
        openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        safe_policies = convert_mongo_types(policies)
        policies_json = json.dumps(safe_policies, indent=2)
        
        prompt = f"""
        Here are the user's insurance policies:
        
        {policies_json}
        
        The user describes this situation: "{situation}"
        
        Based on their policies, please analyze:
        1. Which policies could cover this situation
        2. The estimated coverage amount for each applicable policy
        3. Any deductibles or copays that would apply
        4. The recommended order to file claims if multiple policies apply
        5. Any exclusions or limitations that might affect the claim
        
        IMPORTANT: Your response MUST be a valid JSON object with the following structure:
        {{
          "applicable_policies": ["policy_id_1", "policy_id_2"],
          "coverage_details": [
            {{
              "policy_id": "policy_id_1",
              "estimated_coverage": "$500",
              "deductible": "$100",
              "copay": "20%"
            }}
          ],
          "filing_order": ["policy_id_1", "policy_id_2"],
          "limitations": ["Limitation 1", "Limitation 2"],
          "explanation": "Brief explanation of the recommendation"
        }}
        
        Make sure to return data in the exact format specified, with all fields included, even if some are empty arrays.
        All fields must be present in the JSON response.
        The response MUST be valid JSON only without any additional text or formatting.
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful insurance claims assistant providing accurate recommendations based only on the provided policy details. You MUST return data in JSON format with all required fields."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from the response
        try:
            parsed_result = json.loads(content)
            
            # Ensure all required fields are present
            default_structure = {
                "applicable_policies": [],
                "coverage_details": [],
                "filing_order": [],
                "limitations": [],
                "explanation": ""
            }
            
            # Add any missing fields
            for key, default_value in default_structure.items():
                if key not in parsed_result:
                    parsed_result[key] = default_value
            
            return parsed_result
                
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from OpenAI response")
            # Try to extract key fields from the text response
            fallback_result = {
                "applicable_policies": [],
                "coverage_details": [],
                "filing_order": [],
                "limitations": [],
                "explanation": content.strip()
            }
            
            # Try to extract limitations if available
            if "Important Limitations" in content:
                limitations_text = content.split("Important Limitations")[1].strip()
                limitations = [line.strip('- ').strip() for line in limitations_text.split('\n') if line.strip()]
                fallback_result["limitations"] = limitations
                
            return fallback_result
            
    except Exception as e:
        logger.error(f"Error generating recommendations with OpenAI: {e}")
        return {
            "applicable_policies": [],
            "coverage_details": [],
            "filing_order": [], 
            "limitations": [],
            "explanation": "I encountered an error while analyzing your situation."
        }

async def recommend_claim_options_gemini(policies: List[Dict], situation: str) -> Dict:
    """Recommend claim options using Google Gemini"""
    if not USE_GOOGLE_GEMINI or not GOOGLE_GEMINI_API_KEY:
        return await recommend_claim_options_openai(policies, situation)

    try:
        safe_policies = convert_mongo_types(policies)
        policies_json = json.dumps(safe_policies, indent=2)
        
        prompt = f"""
        Here are the user's insurance policies:
        
        {policies_json}
        
        The user describes this situation: "{situation}"
        
        Based on their policies, please analyze:
        1. Which policies could cover this situation
        2. The estimated coverage amount for each applicable policy
        3. Any deductibles or copays that would apply
        4. The recommended order to file claims if multiple policies apply
        5. Any exclusions or limitations that might affect the claim
        
        IMPORTANT: Your response MUST be a valid JSON object with the following structure:
        {{
          "applicable_policies": ["policy_id_1", "policy_id_2"],
          "coverage_details": [
            {{
              "policy_id": "policy_id_1",
              "estimated_coverage": "$500",
              "deductible": "$100",
              "copay": "20%"
            }}
          ],
          "filing_order": ["policy_id_1", "policy_id_2"],
          "limitations": ["Limitation 1", "Limitation 2"],
          "explanation": "Brief explanation of the recommendation"
        }}
        
        Make sure to return data in the exact format specified, with all fields included, even if some are empty arrays.
        All fields must be present in the JSON response.
        The response MUST be valid JSON only without any additional text or formatting.
        """
        
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1500,
            "response_mime_type": "application/json",
        }
        
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        content = response.text
        
        try:
            # Parse the JSON response
            parsed_result = json.loads(content)
            
            # Ensure all required fields are present
            default_structure = {
                "applicable_policies": [],
                "coverage_details": [],
                "filing_order": [],
                "limitations": [],
                "explanation": ""
            }
            
            # Add any missing fields
            for key, default_value in default_structure.items():
                if key not in parsed_result:
                    parsed_result[key] = default_value
            
            return parsed_result
                
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from Gemini response")
            # Try to extract key fields from the text response
            fallback_result = {
                "applicable_policies": [],
                "coverage_details": [],
                "filing_order": [],
                "limitations": [],
                "explanation": content.strip()
            }
            
            # Try to extract limitations if available
            if "Important Limitations" in content:
                limitations_text = content.split("Important Limitations")[1].strip()
                limitations = [line.strip('- ').strip() for line in limitations_text.split('\n') if line.strip()]
                fallback_result["limitations"] = limitations
                
            return fallback_result
            
    except Exception as e:
        logger.error(f"Error generating recommendations with Gemini: {e}")
        # Fall back to OpenAI
        return await recommend_claim_options_openai(policies, situation)
