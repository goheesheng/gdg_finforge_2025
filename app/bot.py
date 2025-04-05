import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, BinaryIO, Union

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.markdown import hbold
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.config import TELEGRAM_BOT_TOKEN, TEMP_DOWNLOAD_PATH
from app.utils import pdf_utils
from app.services import ocr_service, nlp_service, claim_service
from app.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# State machine for different user flows
class UserStates(StatesGroup):
    main_menu = State()
    uploading_policy = State()
    asking_question = State()
    creating_claim = State()
    entering_situation = State()
    reviewing_claim = State()
    tracking_claim = State()
    filling_claim_form = State()

# Create main menu keyboard
async def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get the main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="📄 Upload Policy", callback_data="upload_policy"),
            InlineKeyboardButton(text="❓ Ask a Question", callback_data="ask_question")
        ],
        [
            InlineKeyboardButton(text="📝 Create Claim", callback_data="create_claim"),
            InlineKeyboardButton(text="📊 Track Claims", callback_data="track_claims")
        ],
        [
            InlineKeyboardButton(text="🔍 Claim Recommendations", callback_data="claim_recommendations"),
            InlineKeyboardButton(text="📋 My Policies", callback_data="my_policies")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """
    Handle the /start command - entry point for users
    """
    user_id = message.from_user.id
    user_data = {
        "user_id": user_id,
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "language_code": message.from_user.language_code,
    }
    
    # Create or update user in database
    await db.create_user(user_data)
    
    await state.set_state(UserStates.main_menu)
    
    welcome_text = (
        f"Hello, {hbold(message.from_user.first_name)}! 👋\n\n"
        f"I'm your Insurance Claim Assistant. I can help you understand your insurance policies, "
        f"recommend claims based on your situation, and assist with filing claims.\n\n"
        f"What would you like to do today?"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=await get_main_menu_keyboard()
    )

@router.message(Command("menu"))
async def show_main_menu(message: Message, state: FSMContext) -> None:
    """Show the main menu"""
    await state.set_state(UserStates.main_menu)
    await message.answer(
        "Main Menu - What would you like to do?",
        reply_markup=await get_main_menu_keyboard()
    )

# Callback query handlers for menu buttons
@router.callback_query(lambda c: c.data == "upload_policy")
async def upload_policy_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the upload policy button"""
    await callback_query.answer()
    await state.set_state(UserStates.uploading_policy)
    await callback_query.message.answer(
        "Please upload your insurance policy document (PDF or image).\n\n"
        "I'll analyze it and extract the key details for you."
    )

@router.callback_query(lambda c: c.data == "ask_question")
async def ask_question_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the ask question button"""
    user_id = callback_query.from_user.id
    
    # Check if user has any policies
    policies = await db.get_policies(user_id)
    if not policies:
        await callback_query.answer("You don't have any policies uploaded yet", show_alert=True)
        return
        
    await callback_query.answer()
    
    # Get list of policies for user to choose from
    policy_keyboard = []
    for policy in policies:
        policy_name = policy.get("provider", "Unknown") + " - " + policy.get("policy_type", "Policy")
        policy_keyboard.append([
            InlineKeyboardButton(
                text=policy_name, 
                callback_data=f"policy_{str(policy['_id'])}"
            )
        ])
    
    policy_keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
    policy_markup = InlineKeyboardMarkup(inline_keyboard=policy_keyboard)
    
    await state.set_state(UserStates.asking_question)
    await callback_query.message.answer(
        "Which policy would you like to ask about?",
        reply_markup=policy_markup
    )

@router.callback_query(lambda c: c.data == "create_claim")
async def create_claim_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the create claim button"""
    user_id = callback_query.from_user.id
    
    # Check if user has any policies
    policies = await db.get_policies(user_id)
    if not policies:
        await callback_query.answer("You don't have any policies uploaded yet", show_alert=True)
        return
        
    await callback_query.answer()
    
    # Get list of policies for user to choose from
    policy_keyboard = []
    for policy in policies:
        policy_name = policy.get("provider", "Unknown") + " - " + policy.get("policy_type", "Policy")
        policy_keyboard.append([
            InlineKeyboardButton(
                text=policy_name, 
                callback_data=f"claim_policy_{str(policy['_id'])}"
            )
        ])
    
    policy_keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
    policy_markup = InlineKeyboardMarkup(inline_keyboard=policy_keyboard)
    
    await state.set_state(UserStates.creating_claim)
    await callback_query.message.answer(
        "Which policy would you like to file a claim for?",
        reply_markup=policy_markup
    )

@router.callback_query(lambda c: c.data == "track_claims")
async def track_claims_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the track claims button"""
    user_id = callback_query.from_user.id
    
    # Get user's claims
    claims = await db.get_claims(user_id)
    await callback_query.answer()
    
    if not claims:
        await callback_query.message.answer(
            "You don't have any claims yet. Use the 'Create Claim' option to file a new claim.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    # Display claims with their statuses
    claims_text = "Your Claims:\n\n"
    claim_keyboard = []
    
    for i, claim in enumerate(claims, 1):
        policy = await db.get_policy(claim.get("policy_id"))
        policy_name = policy.get("provider", "Unknown") if policy else "Unknown"
        
        claims_text += (
            f"{i}. {claim.get('claim_type', 'Claim')}\n"
            f"   Provider: {policy_name}\n"
            f"   Status: {claim.get('status', 'Unknown')}\n"
            f"   Amount: ${claim.get('amount', 0):.2f}\n"
            f"   Date: {claim.get('created_at').strftime('%Y-%m-%d') if claim.get('created_at') else 'Unknown'}\n\n"
        )
        
        claim_keyboard.append([
            InlineKeyboardButton(
                text=f"Claim #{i} - {claim.get('status', 'Unknown')}", 
                callback_data=f"view_claim_{str(claim['_id'])}"
            )
        ])
    
    claim_keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
    claim_markup = InlineKeyboardMarkup(inline_keyboard=claim_keyboard)
    
    await state.set_state(UserStates.tracking_claim)
    await callback_query.message.answer(
        claims_text,
        reply_markup=claim_markup
    )

@router.callback_query(lambda c: c.data == "claim_recommendations")
async def claim_recommendations_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the claim recommendations button"""
    user_id = callback_query.from_user.id
    
    # Check if user has any policies
    policies = await db.get_policies(user_id)
    if not policies:
        await callback_query.answer("You don't have any policies uploaded yet", show_alert=True)
        return
        
    await callback_query.answer()
    await state.set_state(UserStates.entering_situation)
    await callback_query.message.answer(
        "Please describe your medical situation or expense, and I'll recommend which "
        "insurance policies you can claim from.\n\n"
        "For example: 'I visited a chiropractor after a car accident' or "
        "'I need prescription glasses.'"
    )

@router.callback_query(lambda c: c.data == "my_policies")
async def my_policies_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the my policies button"""
    user_id = callback_query.from_user.id
    
    # Get user's policies
    policies = await db.get_policies(user_id)
    await callback_query.answer()
    
    if not policies:
        await callback_query.message.answer(
            "You don't have any policies uploaded yet. Use the 'Upload Policy' option to add one.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    # Display policies with their details
    policies_text = "Your Policies:\n\n"
    policy_keyboard = []
    
    for i, policy in enumerate(policies, 1):
        policies_text += (
            f"{i}. {policy.get('provider', 'Unknown')} - {policy.get('policy_type', 'Policy')}\n"
            f"   Policy Number: {policy.get('policy_number', 'Unknown')}\n"
            f"   Coverage: {', '.join(policy.get('coverage_areas', {}).keys()) if policy.get('coverage_areas') else 'Unknown'}\n\n"
        )
        
        policy_keyboard.append([
            InlineKeyboardButton(
                text=f"{policy.get('provider', 'Unknown')} - {policy.get('policy_type', 'Policy')}", 
                callback_data=f"view_policy_{str(policy['_id'])}"
            )
        ])
    
    policy_keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
    policy_markup = InlineKeyboardMarkup(inline_keyboard=policy_keyboard)
    
    await callback_query.message.answer(
        policies_text,
        reply_markup=policy_markup
    )

@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the back to menu button"""
    await callback_query.answer()
    await state.set_state(UserStates.main_menu)
    await callback_query.message.answer(
        "Main Menu - What would you like to do?",
        reply_markup=await get_main_menu_keyboard()
    )

# Handle policy document uploads
@router.message(UserStates.uploading_policy, lambda message: message.document or message.photo)
async def handle_policy_upload(message: Message, state: FSMContext) -> None:
    """Handle uploaded policy documents"""
    # Send a processing message
    processing_message = await message.answer("Processing your policy document... This may take a minute.")
    
    file_obj = None
    file_id = None
    file_name = None
    file_path = None
    
    try:
        # Handle different types of uploads (document or photo)
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
            # Check if it's a PDF or supported image
            mime_type = message.document.mime_type
            if mime_type not in ["application/pdf", "image/jpeg", "image/png"]:
                await message.answer(
                    "Sorry, I can only process PDF files or images. Please upload a supported file type.",
                    reply_markup=await get_main_menu_keyboard()
                )
                await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
                return
        else:  # Photo
            # Get the best quality photo
            file_id = message.photo[-1].file_id
            file_name = f"photo_{file_id}.jpg"
        
        # Download the file
        file = await bot.get_file(file_id)
        file_path_from_bot = file.file_path
        downloaded = await bot.download_file(file_path_from_bot)
        
        # Save the file locally
        file_path = TEMP_DOWNLOAD_PATH / file_name
        TEMP_DOWNLOAD_PATH.mkdir(exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(downloaded.read())
        
        # Extract text from the file
        extracted_text = await ocr_service.extract_text_from_file(file_path)
        
        if not extracted_text:
            await message.answer(
                "I couldn't extract any text from the uploaded document. Please try a clearer image or a properly formatted PDF.",
                reply_markup=await get_main_menu_keyboard()
            )
            await state.set_state(UserStates.main_menu)
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
            return
        
        # Use NLP to extract structured policy details
        policy_details = await nlp_service.extract_policy_details(extracted_text)
        
        if not policy_details:
            await message.answer(
                "I couldn't understand the insurance policy details from the document. "
                "Please upload a clearer document, or one with more standard formatting.",
                reply_markup=await get_main_menu_keyboard()
            )
            await state.set_state(UserStates.main_menu)
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
            return
        
        # Store the extracted policy details in the database
        policy_data = {
            "file_name": file_name,
            "extracted_text": extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
            **policy_details
        }
        
        saved_policy = await db.save_policy(message.from_user.id, policy_data)
        
        # Delete the processing message
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        
        # Format a summary of the extracted details
        summary = "I've analyzed your policy and extracted the following details:\n\n"
        
        if "provider" in policy_details:
            summary += f"📋 Provider: {policy_details['provider']}\n"
        
        if "policy_number" in policy_details:
            summary += f"🔢 Policy Number: {policy_details['policy_number']}\n"
        
        if "policy_holder" in policy_details:
            summary += f"👤 Policy Holder: {policy_details['policy_holder']}\n"
        
        if "premium" in policy_details:
            summary += f"💰 Premium: {policy_details['premium']}\n"
            
        if "coverage_period" in policy_details:
            coverage = policy_details["coverage_period"]
            start = coverage.get("start", "Unknown")
            end = coverage.get("end", "Unknown")
            summary += f"📅 Coverage Period: {start} to {end}\n"
        
        if "coverage_areas" in policy_details and policy_details["coverage_areas"]:
            summary += "\n✅ Key Coverage Areas:\n"
            for area, details in policy_details["coverage_areas"].items():
                limit = details.get("limit", "Not specified")
                summary += f"- {area}: {limit}\n"
        
        if "exclusions" in policy_details and policy_details["exclusions"]:
            summary += "\n❌ Key Exclusions:\n"
            for exclusion in policy_details["exclusions"][:5]:  # Limit to 5 exclusions
                summary += f"- {exclusion}\n"
            
            if len(policy_details["exclusions"]) > 5:
                summary += f"- ... and {len(policy_details['exclusions']) - 5} more\n"
        
        await message.answer(summary)
        
        # Offer next steps
        await message.answer(
            "Your policy has been saved! You can now:\n"
            "• Ask questions about your coverage\n"
            "• Create a claim\n"
            "• Get claim recommendations based on your situation",
            reply_markup=await get_main_menu_keyboard()
        )
        
        await state.set_state(UserStates.main_menu)
        
    except Exception as e:
        logger.error(f"Error processing policy upload: {e}")
        await message.answer(
            "Sorry, I encountered an error while processing your document. Please try again later.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
    
    finally:
        # Clean up the file
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")

# Handle policy questions
@router.callback_query(lambda c: c.data.startswith("policy_"))
async def policy_question_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle policy selection for asking questions"""
    policy_id = callback_query.data.split("_")[1]
    
    # Store the selected policy ID in state
    await state.update_data(selected_policy_id=policy_id)
    
    await callback_query.answer()
    await callback_query.message.answer(
        "What would you like to know about this policy? Ask me anything about coverage, exclusions, limits, etc."
    )

@router.message(UserStates.asking_question)
async def handle_policy_question(message: Message, state: FSMContext) -> None:
    """Handle questions about policies"""
    user_data = await state.get_data()
    policy_id = user_data.get("selected_policy_id")
    
    if not policy_id:
        await message.answer(
            "I'm not sure which policy you're asking about. Please select a policy first.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    # Get the policy details
    policy = await db.get_policy(policy_id)
    if not policy:
        await message.answer(
            "Sorry, I couldn't find that policy. Please try again.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    # Send a processing message
    processing_message = await message.answer("Analyzing your question...")
    
    try:
        # Use the NLP service to answer the question
        answer = await nlp_service.answer_question_about_policy(policy, message.text)
        
        # Save the Q&A interaction to history
        await db.save_chat_message(
            message.from_user.id,
            {
                "role": "user",
                "content": message.text,
                "policy_id": policy_id
            }
        )
        
        await db.save_chat_message(
            message.from_user.id,
            {
                "role": "assistant",
                "content": answer,
                "policy_id": policy_id
            }
        )
        
        # Delete the processing message
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        
        # Create a keyboard with options to ask another question or go back to menu
        keyboard = [
            [InlineKeyboardButton(text="Ask Another Question", callback_data=f"policy_{policy_id}")],
            [InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")]
        ]
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await message.answer(answer, reply_markup=keyboard_markup)
        
    except Exception as e:
        logger.error(f"Error answering policy question: {e}")
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        await message.answer(
            "I'm sorry, I encountered an error while processing your question. Please try again later.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)

# Handle claim recommendations
@router.message(UserStates.entering_situation)
async def handle_situation_description(message: Message, state: FSMContext) -> None:
    """Process the user's situation to recommend claim options"""
    user_id = message.from_user.id
    situation = message.text
    
    # Send a processing message
    processing_message = await message.answer("Analyzing your situation...")
    
    try:
        # Get claim recommendations
        result = await claim_service.analyze_optimal_claim_path(user_id, situation)
        
        # Delete the processing message
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        
        if not result["success"]:
            await message.answer(
                result["message"],
                reply_markup=await get_main_menu_keyboard()
            )
            await state.set_state(UserStates.main_menu)
            return
        
        recommendations = result["recommendations"]
        
        # Format the recommendations into a user-friendly message
        if "applicable_policies" in recommendations and recommendations["applicable_policies"]:
            response = "Based on your situation, here are my recommendations:\n\n"
            
            if "explanation" in recommendations:
                response += f"{recommendations['explanation']}\n\n"
                
            response += "📋 Applicable Policies:\n"
            policies = await db.get_policies(user_id)
            policy_map = {str(p["_id"]): p for p in policies}
            
            for policy_id in recommendations["applicable_policies"]:
                policy = policy_map.get(policy_id)
                if policy:
                    provider = policy.get("provider", "Unknown")
                    policy_type = policy.get("policy_type", "Policy")
                    response += f"• {provider} - {policy_type}\n"
            
            if "coverage_details" in recommendations:
                response += "\n💰 Coverage Details:\n"
                for detail in recommendations["coverage_details"]:
                    policy_id = detail.get("policy_id")
                    policy = policy_map.get(policy_id)
                    if policy:
                        provider = policy.get("provider", "Unknown")
                        estimated = detail.get("estimated_coverage", "Unknown")
                        deductible = detail.get("deductible", "Unknown")
                        copay = detail.get("copay", "Unknown")
                        
                        response += f"• {provider}:\n"
                        response += f"  - Estimated coverage: {estimated}\n"
                        response += f"  - Deductible: {deductible}\n"
                        response += f"  - Copay/Coinsurance: {copay}\n"
            
            if "filing_order" in recommendations and recommendations["filing_order"]:
                response += "\n📝 Recommended Filing Order:\n"
                for i, policy_id in enumerate(recommendations["filing_order"], 1):
                    policy = policy_map.get(policy_id)
                    if policy:
                        provider = policy.get("provider", "Unknown")
                        response += f"{i}. {provider}\n"
            
            if "limitations" in recommendations:
                response += "\n⚠️ Important Limitations:\n"
                response += f"{recommendations['limitations']}\n"
            
            # Create a keyboard with policies to create claims for
            keyboard = []
            
            for policy_id in recommendations["applicable_policies"]:
                policy = policy_map.get(policy_id)
                if policy:
                    provider = policy.get("provider", "Unknown")
                    keyboard.append([
                        InlineKeyboardButton(
                            text=f"Create Claim with {provider}", 
                            callback_data=f"claim_policy_{policy_id}"
                        )
                    ])
            
            keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
            keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await message.answer(response, reply_markup=keyboard_markup)
        else:
            await message.answer(
                "Based on your situation and the policies you've uploaded, I couldn't find any applicable coverage. "
                "You may want to consult directly with your insurance provider for more specific information.",
                reply_markup=await get_main_menu_keyboard()
            )
        
        await state.set_state(UserStates.main_menu)
        
    except Exception as e:
        logger.error(f"Error generating claim recommendations: {e}")
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        await message.answer(
            "I'm sorry, I encountered an error while analyzing your situation. Please try again later.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)

# Handle claim creation
@router.callback_query(lambda c: c.data.startswith("claim_policy_"))
async def claim_policy_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle policy selection for creating a claim"""
    policy_id = callback_query.data.split("_")[2]
    
    # Store the selected policy ID in state
    await state.update_data(selected_policy_id=policy_id)
    
    # Get policy details for context
    policy = await db.get_policy(policy_id)
    
    await callback_query.answer()
    
    # Create a form to collect claim information
    claim_types = []
    if policy and "coverage_areas" in policy:
        claim_types = list(policy["coverage_areas"].keys())
    
    if not claim_types:
        claim_types = ["Medical", "Dental", "Vision", "Prescription", "Hospital", "Emergency", "Other"]
    
    # Create keyboard with claim types
    keyboard = []
    for claim_type in claim_types:
        keyboard.append([
            InlineKeyboardButton(
                text=claim_type, 
                callback_data=f"claim_type_{claim_type}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await state.set_state(UserStates.creating_claim)
    await callback_query.message.answer(
        "What type of claim would you like to create?",
        reply_markup=keyboard_markup
    )

@router.callback_query(lambda c: c.data.startswith("claim_type_"))
async def claim_type_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle claim type selection"""
    claim_type = callback_query.data.split("_")[2]
    
    # Store the selected claim type in state
    await state.update_data(claim_type=claim_type)
    
    await callback_query.answer()
    await callback_query.message.answer(
        f"Please provide the following information for your {claim_type} claim:\n\n"
        f"1. Date of service (YYYY-MM-DD)\n"
        f"2. Provider name\n"
        f"3. Amount\n"
        f"4. Brief description of the service\n\n"
        f"Example: 2023-05-15, Dr. Smith, 120.50, Annual checkup"
    )
    
    await state.set_state(UserStates.filling_claim_form)

@router.message(UserStates.filling_claim_form)
async def handle_claim_form_submission(message: Message, state: FSMContext) -> None:
    """Process the claim form submission"""
    user_data = await state.get_data()
    policy_id = user_data.get("selected_policy_id")
    claim_type = user_data.get("claim_type")
    
    if not policy_id or not claim_type:
        await message.answer(
            "I'm missing some information about your claim. Let's start over.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    # Parse the claim information from the message
    try:
        # Try to parse the comma-separated values
        parts = [part.strip() for part in message.text.split(",")]
        
        if len(parts) < 4:
            raise ValueError("Not enough information provided")
        
        service_date = parts[0]
        provider_name = parts[1]
        try:
            amount = float(parts[2].replace("$", "").strip())
        except ValueError:
            amount = 0.0
        
        description = parts[3]
        
        # Create the claim data
        claim_data = {
            "policy_id": policy_id,
            "claim_type": claim_type,
            "service_date": service_date,
            "provider_name": provider_name,
            "amount": amount,
            "description": description,
            "status": "pending"
        }
        
        # Save the claim
        created_claim = await db.create_claim(message.from_user.id, claim_data)
        
        if not created_claim:
            raise ValueError("Failed to create claim")
        
        # Generate a claim form
        form_path = await claim_service.generate_claim_form(
            message.from_user.id, 
            policy_id, 
            claim_data
        )
        
        # Send a success message
        await message.answer(
            f"✅ Your claim has been created successfully!\n\n"
            f"Claim Type: {claim_type}\n"
            f"Provider: {provider_name}\n"
            f"Amount: ${amount:.2f}\n"
            f"Status: Pending\n\n"
            f"You can track the status of your claim using the 'Track Claims' option."
        )
        
        # Send the claim form if it was generated
        if form_path:
            await message.answer("Here's your completed claim form:")
            await message.answer_document(FSInputFile(form_path))
            
            # Clean up the file
            try:
                form_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting claim form file {form_path}: {e}")
        
        # Return to main menu
        await message.answer(
            "What would you like to do next?",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        
    except Exception as e:
        logger.error(f"Error creating claim: {e}")
        await message.answer(
            "I couldn't process your claim information. Please make sure it's in the format:\n"
            "Date (YYYY-MM-DD), Provider name, Amount, Description\n\n"
            "For example: 2023-05-15, Dr. Smith, 120.50, Annual checkup\n\n"
            "Please try again or go back to the main menu with /menu."
        )

# Handle viewing policy details
@router.callback_query(lambda c: c.data.startswith("view_policy_"))
async def view_policy_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle viewing policy details"""
    policy_id = callback_query.data.split("_")[2]
    
    # Get policy details
    policy = await db.get_policy(policy_id)
    
    await callback_query.answer()
    
    if not policy:
        await callback_query.message.answer(
            "Sorry, I couldn't find that policy. Please try again.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    # Format the policy details
    details = f"📋 Policy Details: {policy.get('provider', 'Unknown')}\n\n"
    
    if "policy_number" in policy:
        details += f"Policy Number: {policy['policy_number']}\n"
    
    if "policy_holder" in policy:
        details += f"Policy Holder: {policy['policy_holder']}\n"
    
    if "premium" in policy:
        details += f"Premium: {policy['premium']}\n"
        
    if "coverage_period" in policy:
        coverage = policy["coverage_period"]
        start = coverage.get("start", "Unknown")
        end = coverage.get("end", "Unknown")
        details += f"Coverage Period: {start} to {end}\n"
    
    if "deductibles" in policy:
        details += f"\nDeductibles: {policy['deductibles']}\n"
    
    if "out_of_pocket_max" in policy:
        details += f"Out-of-Pocket Maximum: {policy['out_of_pocket_max']}\n"
    
    if "coverage_areas" in policy and policy["coverage_areas"]:
        details += "\n✅ Coverage Areas:\n"
        for area, details_info in policy["coverage_areas"].items():
            limit = details_info.get("limit", "Not specified")
            details += f"- {area}: {limit}\n"
    
    if "exclusions" in policy and policy["exclusions"]:
        details += "\n❌ Exclusions:\n"
        for exclusion in policy["exclusions"]:
            details += f"- {exclusion}\n"
    
    if "special_conditions" in policy and policy["special_conditions"]:
        details += "\n⚠️ Special Conditions:\n"
        for condition in policy["special_conditions"]:
            details += f"- {condition}\n"
    
    # Create a keyboard with options
    keyboard = [
        [InlineKeyboardButton(text="Ask a Question", callback_data=f"policy_{policy_id}")],
        [InlineKeyboardButton(text="Create a Claim", callback_data=f"claim_policy_{policy_id}")],
        [InlineKeyboardButton(text="← Back to Policies", callback_data="my_policies")],
        [InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")]
    ]
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.answer(details, reply_markup=keyboard_markup)

# Handle viewing claim details
@router.callback_query(lambda c: c.data.startswith("view_claim_"))
async def view_claim_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle viewing claim details"""
    claim_id = callback_query.data.split("_")[2]
    
    # Get claim details
    result = await claim_service.track_claim_status(claim_id)
    
    await callback_query.answer()
    
    if not result["success"]:
        await callback_query.message.answer(
            result["message"],
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        return
    
    claim = result["claim"]
    
    # Get policy details
    policy = await db.get_policy(claim.get("policy_id"))
    policy_name = policy.get("provider", "Unknown") if policy else "Unknown"
    
    # Format the claim details
    details = f"📝 Claim Details\n\n"
    details += f"Type: {claim.get('claim_type', 'Unknown')}\n"
    details += f"Provider: {claim.get('provider_name', 'Unknown')}\n"
    details += f"Policy: {policy_name}\n"
    details += f"Service Date: {claim.get('service_date', 'Unknown')}\n"
    details += f"Amount: ${claim.get('amount', 0):.2f}\n"
    details += f"Status: {claim.get('status', 'Unknown')}\n"
    
    if "description" in claim:
        details += f"\nDescription: {claim['description']}\n"
    
    if "notes" in claim:
        details += f"\nNotes: {claim['notes']}\n"
        
    created_at = claim.get("created_at")
    if created_at:
        details += f"\nSubmitted: {created_at.strftime('%Y-%m-%d %H:%M')}\n"
    
    updated_at = claim.get("updated_at")
    if updated_at:
        details += f"Last Updated: {updated_at.strftime('%Y-%m-%d %H:%M')}\n"
    
    # Create a keyboard with options
    keyboard = [
        [InlineKeyboardButton(text="← Back to Claims", callback_data="track_claims")],
        [InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")]
    ]
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.answer(details, reply_markup=keyboard_markup)

# Run the bot
async def main() -> None:
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create temp directory if it doesn't exist
    TEMP_DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
    
    # Start the bot
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
