import json
import logging
from typing import Dict, List, Optional, Any, Union
import os
import re
from openai import OpenAI, AsyncOpenAI

from app.config.config import (
    OPENAI_API_KEY, 
    USE_GOOGLE_GEMINI, 
    GOOGLE_GEMINI_API_KEY
)

logger = logging.getLogger(__name__)

# Initialize OpenAI
openai_client = None
if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Initialize Google Gemini if enabled
if USE_GOOGLE_GEMINI and GOOGLE_GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-pro')
    except ImportError:
        logger.warning("Google Gemini library not available. Falling back to OpenAI.")
        USE_GOOGLE_GEMINI = False
    except Exception as e:
        logger.error(f"Failed to initialize Google Gemini: {e}")
        USE_GOOGLE_GEMINI = False

async def extract_policy_details_openai(policy_text: str) -> Dict:
    """Extract policy details using OpenAI GPT"""
    if not OPENAI_API_KEY or not openai_client:
        logger.error("OpenAI API key not provided")
        return {}

    try:
        prompt = f"""
        You are a specialized insurance document parser. Extract the key information from this insurance policy text:
        
        {policy_text[:15000]}  # Increased limit to capture more context
        
        When analyzing insurance policies, pay special attention to:
        1. Tables with coverage limits, co-pay amounts, and deductibles
        2. Policy numbers, often formatted like HS-xxxxxxxxx or similar patterns
        3. Date formats which may be inconsistent (MM/DD/YYYY, DD-MM-YYYY, etc.)
        4. Currency values which may have formatting issues
        
        Please extract and organize the following information in a structured JSON format:
        
        1. Policy provider/company name (look for insurance company letterhead or branding)
        2. Policy ID/number (search for formats like: HS-xxxxxxxxx, Policy #, Policy Number, etc.)
        3. Policy holder name (listed as "insured", "member", "policyholder", etc.)
        4. Coverage period (start and end dates - look for "effective date", "policy period", etc.)
        5. Premium amount (usually with currency symbol or listed as "premium")
        6. Coverage areas with their limits (extract details from tables if present)
           - For each coverage area include: limit amount, deductible, co-pay percentage/amount
        7. Exclusions (what's not covered - often in a separate section)
        8. Deductibles (yearly or per-visit amounts)
        9. Copayments or coinsurance details (amounts or percentages)
        10. Out-of-pocket maximums
        
        If you can't find specific information, use null values rather than making assumptions.
        Format all currency values consistently (e.g., "CAD 100" or "$100 CAD").
        
        Use this exact JSON structure:
        {{
            "provider": "string",
            "policy_number": "string",
            "policy_holder": "string",
            "policy_type": "string",
            "coverage_period": {{
                "start": "string (YYYY-MM-DD format if possible)",
                "end": "string (YYYY-MM-DD format if possible)"
            }},
            "premium": "string (with currency)",
            "coverage_areas": {{
                "area_name": {{
                    "limit": "string",
                    "deductible": "string",
                    "copay": "string",
                    "notes": "string"
                }},
                // more areas
            }},
            "exclusions": ["string"],
            "deductible": "string",
            "out_of_pocket_max": "string",
            "special_conditions": ["string"]
        }}
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert insurance policy parser that extracts structured data from document text. You pay special attention to tabular data and policy details in insurance documents."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.2  # Lower temperature for more deterministic extraction
        )
        
        content = response.choices[0].message.content
        
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
            
            # Try a fallback approach to recover data even with JSON parsing failure
            try:
                # Attempt to extract key details using regex patterns
                fallback_data = {}
                
                # Extract policy number
                policy_match = re.search(r'[Pp]olicy\s*(?:#|[Nn]o|[Nn]umber)[:.]\s*([A-Z0-9-]{5,20})', policy_text)
                if policy_match:
                    fallback_data["policy_number"] = policy_match.group(1)
                
                # Extract provider name
                provider_match = re.search(r'(?:insurer|provider|company)[:\s]+([A-Za-z\s&]+(?:Insurance|Health|Life)(?:\s[A-Za-z&]+){0,3})', policy_text, re.IGNORECASE)
                if provider_match:
                    fallback_data["provider"] = provider_match.group(1).strip()
                
                # Extract dates for coverage period
                dates = re.findall(r'(?:from|start|period|date).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}).*?(?:to|end|through).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', policy_text, re.IGNORECASE)
                if dates:
                    fallback_data["coverage_period"] = {
                        "start": dates[0][0],
                        "end": dates[0][1]
                    }
                
                return {"raw_extraction": content, **fallback_data}
            except Exception as e:
                logger.error(f"Fallback extraction failed: {e}")
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
    if not OPENAI_API_KEY or not openai_client:
        logger.error("OpenAI API key not provided")
        return "I'm sorry, I cannot answer questions about your policy right now due to configuration issues."

    try:
        policy_json = json.dumps(policy_details, indent=2)
        
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
        policy_json = json.dumps(policy_details, indent=2)
        
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
    if not OPENAI_API_KEY or not openai_client:
        logger.error("OpenAI API key not provided")
        return {"recommendations": [], "message": "Unable to provide recommendations due to configuration issues."}

    try:
        policies_json = json.dumps(policies, indent=2)
        
        prompt = f"""
        The user has the following insurance policies:
        
        {policies_json}
        
        The user describes their situation as follows: "{situation}"
        
        Based on their coverage, please:
        1. Analyze if their situation is covered by any of their policies
        2. Recommend which policy or policies they should file a claim with
        3. Explain why you recommend this approach
        4. Include any potential exclusions or limitations they should be aware of
        
        Return your response as a JSON object with the following structure:
        {{
            "covered": true/false,
            "recommended_policies": ["policy_id1", "policy_id2"],
            "explanation": "Detailed explanation of your recommendation",
            "potential_issues": ["Issue 1", "Issue 2"],
            "estimated_coverage": "Estimated amount that might be covered"
        }}
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert insurance claim analyzer that helps users maximize their coverage benefits."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
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
            return {
                "recommendations": [],
                "message": "I analyzed your situation but couldn't generate a structured recommendation.",
                "raw_analysis": content
            }
            
    except Exception as e:
        logger.error(f"Error generating recommendations with OpenAI: {e}")
        return {"recommendations": [], "message": "I encountered an error while analyzing your situation."}

async def recommend_claim_options_gemini(policies: List[Dict], situation: str) -> Dict:
    """Recommend claim options using Google Gemini"""
    if not USE_GOOGLE_GEMINI or not GOOGLE_GEMINI_API_KEY:
        return await recommend_claim_options_openai(policies, situation)

    try:
        policies_json = json.dumps(policies, indent=2)
        
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
        
        Provide recommendations in a structured JSON format with these fields:
        - applicable_policies: array of policy IDs that apply
        - coverage_details: array of objects with policy_id, estimated_coverage, deductible, copay
        - filing_order: recommended sequence of policies to file claims with
        - limitations: any important limitations or exclusions
        - explanation: brief explanation of the recommendation
        
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
            return {
                "recommendations": [],
                "message": "I analyzed your situation but couldn't generate a structured recommendation.",
                "raw_analysis": content
            }
            
    except Exception as e:
        logger.error(f"Error generating recommendations with Gemini: {e}")
        # Fall back to OpenAI
        return await recommend_claim_options_openai(policies, situation)
