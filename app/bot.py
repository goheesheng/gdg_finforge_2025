import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, BinaryIO, Union
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, types
from aiogram.client.default import DefaultBotProperties
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
#, client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
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
    entering_email = State()
    entering_phone = State()
    entering_name = State()
    
    # Specific claim form states
    claim_date = State()
    claim_provider = State()
    claim_amount = State()
    claim_description = State()

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
        ],
        [
            InlineKeyboardButton(text="👤 My Profile", callback_data="my_profile")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Add this function to check if user profile needs completion
async def check_user_profile(user_id: int) -> Dict[str, bool]:
    """Check if user profile is complete or needs additional info"""
    user = await db.get_user(user_id)
    if not user:
        return {"profile_complete": False, "needs_email": True, "needs_phone": True, "needs_name": True}
        
    # Check if required fields are missing
    needs_email = not bool(user.get("email"))
    needs_phone = not bool(user.get("phone"))
    
    # Check if full name is missing or only Telegram username is present
    has_first_name = bool(user.get("first_name"))
    has_last_name = bool(user.get("last_name"))
    has_full_name = bool(user.get("full_name"))
    
    # If user doesn't have a full name, or has only first name but not last name,
    # prompt for complete name
    needs_name = not has_full_name and (not has_first_name or not has_last_name)
    
    profile_complete = not (needs_email or needs_phone or needs_name)
    
    return {
        "profile_complete": profile_complete,
        "needs_email": needs_email,
        "needs_phone": needs_phone,
        "needs_name": needs_name
    }

# Add this function to prompt for missing information
async def prompt_for_missing_info(message: Union[Message, CallbackQuery], state: FSMContext, user_id: int) -> bool:
    """Prompts user for missing profile information. Returns True if profile is complete."""
    profile_status = await check_user_profile(user_id)
    
    # If profile is complete, nothing to do
    if profile_status["profile_complete"]:
        return True
    
    # Handle missing name
    if profile_status["needs_name"]:
        if isinstance(message, CallbackQuery):
            await message.message.answer("Please enter your full name (first and last name):")
        else:
            await message.answer("Please enter your full name (first and last name):")
        await state.set_state(UserStates.entering_name)
        return False
        
    # Handle missing email
    if profile_status["needs_email"]:
        if isinstance(message, CallbackQuery):
            await message.message.answer("Please provide your email address:")
        else:
            await message.answer("Please provide your email address:")
        await state.set_state(UserStates.entering_email)
        return False
        
    # Handle missing phone
    if profile_status["needs_phone"]:
        if isinstance(message, CallbackQuery):
            await message.message.answer("Please provide your phone number for contact purposes:")
        else:
            await message.answer("Please provide your phone number for contact purposes:")
        await state.set_state(UserStates.entering_phone)
        return False
        
    return True

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    # await client.drop_database("insurance_bot")

    # return
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
    
    # Welcome message first
    welcome_text = (
        f"Hello, {hbold(message.from_user.first_name or 'there')}! 👋\n\n"
        f"I'm your Insurance Claim Assistant. I can help you understand your insurance policies, "
        f"recommend claims based on your situation, and assist with filing claims."
    )
    
    await message.answer(welcome_text)
    
    # Always ask for complete profile information to ensure we have it for claim forms
    await message.answer(
        "To provide you with the best service and ensure your claim forms are correctly filled, "
        "I'd like to collect some basic information.\n\n"
        "Please enter your full name (first and last name):"
    )
    
    # Start collecting profile information
    await state.set_state(UserStates.entering_name)
    # Flag that we're in the initial setup flow
    await state.update_data(continue_to="initial_setup")
    
@router.message(UserStates.entering_name)
async def handle_name_entry(message: Message, state: FSMContext) -> None:
    """Process user's name entry"""
    full_name = message.text.strip()
    user_data = await state.get_data()
    continue_to = user_data.get("continue_to")
    
    if len(full_name) < 3:
        await message.answer("Please enter your complete name (first and last name):")
        return
    
    # Try to split into first and last name
    name_parts = full_name.split(maxsplit=1)
    user_update = {"full_name": full_name}
    
    if len(name_parts) >= 2:
        user_update["first_name"] = name_parts[0]
        user_update["last_name"] = name_parts[1]
    else:
        user_update["first_name"] = full_name
    
    # Update user profile with name
    user_id = message.from_user.id
    await db.update_user(user_id, user_update)
    
    # Send confirmation
    await message.answer(f"Thank you, {full_name}!")
    
    # Check where to continue based on flow
    if continue_to == "profile_update":
        # Return to profile view
        await show_profile(message, user_id, state)
        return
    elif continue_to == "initial_setup":
        # Continue with email collection for initial setup
        await message.answer("Please provide your email address:")
        await state.set_state(UserStates.entering_email)
        return
    
    # Check if we need additional information for claim flow
    profile_status = await check_user_profile(user_id)
    
    # Continue with email collection if needed
    if profile_status["needs_email"]:
        await message.answer("Please provide your email address:")
        await state.set_state(UserStates.entering_email)
        return
        
    # Continue with phone collection if needed
    if profile_status["needs_phone"]:
        await message.answer("Please provide your phone number for contact purposes:")
        await state.set_state(UserStates.entering_phone)
        return
    
    # Check if we're in the middle of a claim flow
    if continue_to == "claim_provider":
        # Continue with claim provider
        await message.answer("Now, what is the name of the healthcare provider or facility?")
        await state.set_state(UserStates.claim_provider)
        return
    
    # Show main menu if not continuing to a specific state
    await state.set_state(UserStates.main_menu)
    await message.answer(
        "Main Menu - What would you like to do?",
        reply_markup=await get_main_menu_keyboard()
    )

@router.message(UserStates.entering_email)
async def handle_email_entry(message: Message, state: FSMContext) -> None:
    """Process user's email entry"""
    email = message.text.strip()
    user_data = await state.get_data()
    continue_to = user_data.get("continue_to")
    
    # Basic email validation
    if not "@" in email or not "." in email or len(email) < 5:
        await message.answer("That doesn't look like a valid email address. Please try again:")
        return
    
    # Update user profile with email
    user_id = message.from_user.id
    await db.update_user(user_id, {"email": email})
    
    # Send confirmation
    await message.answer(f"Thank you! Your email ({email}) has been saved.")
    
    # Check where to continue based on flow
    if continue_to == "profile_update":
        # Return to profile view
        await show_profile(message, user_id, state)
        return
    
    # Always continue with phone collection in the initial flow
    if continue_to == "initial_setup":
        await message.answer("Please provide your phone number for contact purposes:")
        await state.set_state(UserStates.entering_phone)
        return
    
    # Check if we need additional profile information
    profile_status = await check_user_profile(user_id)
    
    # Continue with name collection if needed
    if profile_status["needs_name"]:
        await message.answer("Please enter your full name (first and last name):")
        await state.set_state(UserStates.entering_name)
        return
    
    # Continue with phone collection if needed
    if profile_status["needs_phone"]:
        await message.answer("Please provide your phone number for contact purposes:")
        await state.set_state(UserStates.entering_phone)
        return
    
    # Check if we're in the middle of a claim flow
    if continue_to == "claim_provider":
        # Continue with claim provider
        await message.answer("Now, what is the name of the healthcare provider or facility?")
        await state.set_state(UserStates.claim_provider)
        return
    
    # Show main menu if not continuing to a specific state
    await state.set_state(UserStates.main_menu)
    await message.answer(
        "Main Menu - What would you like to do?",
        reply_markup=await get_main_menu_keyboard()
    )

@router.message(UserStates.entering_phone)
async def handle_phone_entry(message: Message, state: FSMContext) -> None:
    """Process user's phone entry"""
    phone = message.text.strip()
    user_data = await state.get_data()
    continue_to = user_data.get("continue_to")
    
    # Basic phone validation - allow digits, +, -, (, ), and spaces
    cleaned_phone = ''.join(c for c in phone if c.isdigit() or c in '+-() ')
    if len(cleaned_phone) < 7:  # Minimum reasonable length for a phone number
        await message.answer("That doesn't look like a valid phone number. Please try again:")
        return
    
    # Update user profile with phone
    user_id = message.from_user.id
    await db.update_user(user_id, {"phone": cleaned_phone})
    
    # Send confirmation
    await message.answer(f"Thank you! Your phone number has been saved.")
    
    # Check where to continue based on flow
    if continue_to == "profile_update":
        # Return to profile view
        await show_profile(message, user_id, state)
        return
    
    # If this is the initial setup, show the main menu
    if continue_to == "initial_setup":
        await state.set_state(UserStates.main_menu)
        await message.answer(
            "Thank you for providing your information! What would you like to do next?",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    # Check if we're in the middle of a claim flow
    if continue_to == "claim_provider":
        # Continue with claim provider
        await message.answer("Now, what is the name of the healthcare provider or facility?")
        await state.set_state(UserStates.claim_provider)
        return
    
    # Show main menu if not continuing to a specific state
    await state.set_state(UserStates.main_menu)
    await message.answer(
        "Main Menu - What would you like to do?",
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
        
    try:
        await callback_query.answer()
    except Exception as e:
        logger.warning(f"Callback answer failed: {e}")
    
    # Get list of policies for user to choose from
    policy_keyboard = []
    for policy in policies:
        # Try to create a more descriptive policy name using available fields
        provider = policy.get("provider", "")
        policy_type = policy.get("policy_type", "")
        policy_number = policy.get("policy_number", "")
        
        if provider and policy_type:
            policy_name = f"{provider} - {policy_type}"
        elif provider:
            policy_name = provider
        elif policy_type:
            policy_name = f"Policy type: {policy_type}"
        elif policy_number:
            policy_name = f"Policy #{policy_number}"
        else:
            # If no identifying information, use part of the ID
            policy_id = str(policy['_id'])
            policy_name = f"Policy {policy_id[-6:]}"
            
        # Add coverage areas if available
        if policy.get("coverage_areas"):
            areas = list(policy.get("coverage_areas", {}).keys())
            if areas:
                policy_name += f" ({', '.join(areas[:2])})"
                if len(areas) > 2:
                    policy_name += "..."
        
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
        # Try to create a more descriptive policy name using available fields
        provider = policy.get("provider", "")
        policy_type = policy.get("policy_type", "")
        policy_number = policy.get("policy_number", "")
        
        if provider and policy_type:
            policy_name = f"{provider} - {policy_type}"
        elif provider:
            policy_name = provider
        elif policy_type:
            policy_name = f"Policy type: {policy_type}"
        elif policy_number:
            policy_name = f"Policy #{policy_number}"
        else:
            # If no identifying information, use part of the ID
            policy_id = str(policy['_id'])
            policy_name = f"Policy {policy_id[-6:]}"
            
        # Add coverage areas if available
        if policy.get("coverage_areas"):
            areas = list(policy.get("coverage_areas", {}).keys())
            if areas:
                policy_name += f" ({', '.join(areas[:2])})"
                if len(areas) > 2:
                    policy_name += "..."
        
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
        # Get policy details
        policy = await db.get_policy(claim.get("policy_id"))
        
        # Get provider information from multiple possible sources
        provider_name = claim.get('provider_name', '')
        if not provider_name:
            provider_name = claim.get('provider', '')
        if not provider_name and policy:
            provider_name = policy.get('provider', '')
            if not provider_name:
                provider_name = policy.get('company', '')
            if not provider_name:
                provider_name = policy.get('policy_provider', '')
        
        claims_text += (
            f"{i}. {claim.get('claim_type', 'Claim')}\n"
            f"   Provider: {provider_name if provider_name else 'Unknown'}\n"
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
        # Get policy provider and type
        provider = policy.get('policy_provider', '')  # Try 'policy_provider' field first
        if not provider:
            provider = policy.get('company', '')  # Try 'company' field next
        if not provider:
            provider = policy.get('provider', '')  # Fall back to 'provider' field
        policy_type = policy.get('policy_type', 'Policy')
        
        # Get policy number from either policy_number or policy_id field
        policy_number = policy.get('policy_number', '')
        if not policy_number and 'policy_id' in policy:
            policy_number = policy['policy_id']
            
        # Get coverage areas
        coverage_areas = []
        if policy.get('coverage_areas'):
            if isinstance(policy['coverage_areas'], dict):
                coverage_areas = list(policy['coverage_areas'].keys())
            elif isinstance(policy['coverage_areas'], list):
                # Handle list format for coverage areas
                for area in policy['coverage_areas']:
                    if isinstance(area, dict) and 'coverage_type' in area:
                        coverage_areas.append(area['coverage_type'])
        
        # Format the policy display
        policies_text += (
            f"{i}. {provider if provider else 'Unknown'} - {policy_type}\n"
            f"   Policy Number: {policy_number if policy_number else 'Unknown'}\n"
            f"   Coverage: {', '.join(coverage_areas) if coverage_areas else 'Unknown'}\n\n"
        )
        
        # Create button text
        button_text = f"{provider if provider else 'Unknown'} - {policy_type}"
        if policy_number:
            button_text += f" ({policy_number})"
            
        policy_keyboard.append([
            InlineKeyboardButton(
                text=button_text, 
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
    
    # Check if we need additional user info
    profile_complete = await prompt_for_missing_info(callback_query, state, callback_query.from_user.id)
    
    if not profile_complete:
        return
    
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
        
        # Convert coverage_areas from list to dictionary if needed
        if "coverage_areas" in policy_details and isinstance(policy_details["coverage_areas"], list):
            coverage_areas = {}
            for coverage in policy_details["coverage_areas"]:
                # Handle different possible keys for coverage type
                coverage_type = coverage.get('type', coverage.get('coverage_type', '')).lower().replace(' ', '_')
                if not coverage_type:
                    continue
                    
                # Handle different possible formats for limit
                limit = coverage.get('limit', 0)
                if isinstance(limit, str):
                    limit = float(limit.replace('$', '').replace(',', ''))
                    
                coverage_areas[coverage_type] = {
                    'limit': limit,
                    'description': coverage.get('description', '')
                }
            policy_details["coverage_areas"] = coverage_areas
        
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
                if isinstance(details, dict):
                    limit = details.get("limit", "Not specified")
                else:
                    limit = details

                summary += f"• {area.title()}: {limit}\n"

        if "exclusions" in policy_details and policy_details["exclusions"]:
            summary += "\n❌ Key Exclusions:\n"
            for exclusion in policy_details["exclusions"][:5]:
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
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        except Exception as e:
            logger.warning(f"Failed to delete processing message: {e}")
    
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
        
        # Start with a default response
        response = "Based on your situation, here are my recommendations:\n\n"
        
        # Always include the explanation if available
        if recommendations.get("explanation"):
            response += f"{recommendations['explanation']}\n\n"
        
        # Get policies for reference
        policies = await db.get_policies(user_id)
        
        # Create a policy map with both ObjectId and string ID keys for flexibility
        policy_map = {}
        for p in policies:
            str_id = str(p["_id"])
            # Store the policy with both ObjectId and string key for easier lookup
            policy_map[str_id] = p
            policy_map[p["_id"]] = p
            
        logger.info(f"Policy map keys: {list(policy_map.keys())}")
        
        # Format and add applicable policies section
        applicable_policies = recommendations.get("applicable_policies", [])
        logger.info(f"Processing applicable policies: {applicable_policies}")
        
        response += "📋 Applicable Policies:\n"
        if applicable_policies:
            for policy_id in applicable_policies:
                # Try to handle both string and ObjectId
                policy_id_str = str(policy_id)
                policy = policy_map.get(policy_id) or policy_map.get(policy_id_str)
                
                if policy:
                    # Use improved policy naming logic
                    policy_name = get_descriptive_policy_name(policy)
                    response += f"• {policy_name}\n"
                else:
                    # Log the missing policy
                    logger.warning(f"Policy not found for ID: {policy_id}, available IDs: {list(policy_map.keys())}")
                    response += f"• Policy ID: {policy_id} \n"
        else:
            response += "• No specific policies identified\n"
        
        # Format and add coverage details section
        coverage_details = recommendations.get("coverage_details", [])
        response += "\n💰 Coverage Details:\n"
        if coverage_details:
            for detail in coverage_details:
                policy_id = detail.get("policy_id")
                policy_id_str = str(policy_id)
                policy = policy_map.get(policy_id) or policy_map.get(policy_id_str)
                
                if policy:
                    # Use improved policy naming logic
                    policy_name = get_descriptive_policy_name(policy)
                    estimated = detail.get("estimated_coverage", "Unknown")
                    deductible = detail.get("deductible", "Unknown")
                    copay = detail.get("copay", "Unknown")
                    
                    response += f"• {policy_name}:\n"
                    response += f"  - Estimated coverage: {estimated}\n"
                    response += f"  - Deductible: {deductible}\n"
                    response += f"  - Copay/Coinsurance: {copay}\n"
                else:
                    logger.warning(f"Policy not found for coverage detail with ID: {policy_id}")
                    response += f"• Policy ID {policy_id}:\n"
                    response += f"  - Estimated coverage: {detail.get('estimated_coverage', 'Unknown')}\n"
                    response += f"  - Deductible: {detail.get('deductible', 'Unknown')}\n"
                    response += f"  - Copay/Coinsurance: {detail.get('copay', 'Unknown')}\n"
        else:
            response += "• See policy documents for specific coverage details\n"
        
        # Format and add filing order section
        filing_order = recommendations.get("filing_order", [])
        response += "\n📝 Recommended Filing Order:\n"
        if filing_order:
            for i, policy_id in enumerate(filing_order, 1):
                policy_id_str = str(policy_id)
                policy = policy_map.get(policy_id) or policy_map.get(policy_id_str)
                
                if policy:
                    # Use improved policy naming logic
                    policy_name = get_descriptive_policy_name(policy)
                    response += f"{i}. {policy_name}\n"
                else:
                    logger.warning(f"Policy not found for filing order with ID: {policy_id}")
                    response += f"{i}. Policy ID: {policy_id} \n"
        else:
            response += "• No specific filing order recommended\n"
        
        # Format and add limitations section
        limitations = recommendations.get("limitations", [])
        response += "\n⚠️ Important Limitations:\n"
        if limitations:
            for limitation in limitations:
                response += f"• {limitation}\n"
        else:
            response += "• Review your policy documents for specific limitations and exclusions\n"
        
        # Create a keyboard with policies to create claims for
        keyboard = []
        
        for policy_id in applicable_policies:
            policy_id_str = str(policy_id)
            policy = policy_map.get(policy_id) or policy_map.get(policy_id_str)
            
            if policy:
                # Use improved policy naming logic
                policy_name = get_descriptive_policy_name(policy)
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"Create Claim with {policy_name.split(' (')[0]}", 
                        callback_data=f"claim_policy_{policy_id_str}"
                    )
                ])
        
        keyboard.append([InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")])
        keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await message.answer(response, reply_markup=keyboard_markup)
        await state.set_state(UserStates.main_menu)
        
    except Exception as e:
        logger.error(f"Error generating claim recommendations: {e}")
        logger.exception("Full traceback:")
        await bot.delete_message(chat_id=message.chat.id, message_id=processing_message.message_id)
        await message.answer(
            "I'm sorry, I encountered an error while analyzing your situation. Please try again later.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)

# Helper function to get a descriptive policy name
def get_descriptive_policy_name(policy: Dict) -> str:
    """Construct a descriptive policy name using available fields"""
    provider = policy.get("provider", "")
    policy_type = policy.get("policy_type", "")
    policy_number = policy.get("policy_number", "")
    
    # If policy_number is empty, try to get it from policy_id
    if not policy_number and "policy_id" in policy:
        policy_number = policy["policy_id"]
    
    if provider and policy_type:
        policy_name = f"{provider} - {policy_type}"
    elif provider:
        policy_name = provider
    elif policy_type:
        policy_name = f"Policy type: {policy_type}"
    elif policy_number:
        policy_name = f"Policy #{policy_number}"
    else:
        # If no identifying information, use part of the ID
        policy_id = str(policy['_id'])
        policy_name = f"Policy {policy_id[-6:]}"
    
    # Add policy number if available
    if policy_number and policy_number not in policy_name:
        policy_name += f" ({policy_number})"
        
    # Add coverage areas if available
    coverage_areas = []
    if policy.get("coverage_areas"):
        if isinstance(policy["coverage_areas"], dict):
            coverage_areas = list(policy["coverage_areas"].keys())
        elif isinstance(policy["coverage_areas"], list):
            # Handle list format for coverage areas
            for area in policy["coverage_areas"]:
                if isinstance(area, dict) and "coverage_type" in area:
                    coverage_areas.append(area["coverage_type"])
    
    if coverage_areas:
        policy_name += f" ({', '.join(coverage_areas[:2])})"
        if len(coverage_areas) > 2:
            policy_name += "..."
                
    return policy_name

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
    
    # Guide user through form starting with date
    await callback_query.message.answer(
        f"You're creating a {claim_type} claim. Let's fill out the details step by step.\n\n"
        f"First, what was the date of service? (Please use YYYY-MM-DD format)"
    )
    
    # Set state to claim date collection
    await state.set_state(UserStates.claim_date)

@router.message(UserStates.claim_date)
async def handle_claim_date(message: Message, state: FSMContext) -> None:
    """Process the claim date entry"""
    try:
        # Validate date format
        input_date = message.text.strip()
        datetime.strptime(input_date, "%Y-%m-%d")
        await state.update_data(service_date=input_date)
        
        # Confirm date and check if profile is complete
        await message.answer(f"Date of service: {input_date}")
        
        # Check if we need profile information
        user_id = message.from_user.id
        profile_status = await check_user_profile(user_id)
        
        if profile_status["needs_email"]:
            await message.answer("Before we continue, please provide your email address:")
            await state.set_state(UserStates.entering_email)
            # Save that we're in claim flow to return to it later
            await state.update_data(continue_to="claim_provider")
            return
            
        if profile_status["needs_phone"]:
            await message.answer("Please provide your phone number for contact purposes:")
            await state.set_state(UserStates.entering_phone)
            # Save that we're in claim flow to return to it later
            await state.update_data(continue_to="claim_provider")
            return
            
        # If profile is complete, continue with provider
        await message.answer("Great! Now, what is the name of the healthcare provider or facility?")
        await state.set_state(UserStates.claim_provider)
        
    except ValueError:
        await message.answer(
            "Please provide a valid date in YYYY-MM-DD format (e.g., 2023-05-15):"
        )

@router.message(UserStates.claim_provider)
async def handle_claim_provider(message: Message, state: FSMContext) -> None:
    """Process provider name entry"""
    provider_name = message.text.strip()
    if not provider_name:
        await message.answer("Please provide the name of the provider:")
        return
        
    await state.update_data(provider_name=provider_name)
    
    # Move to next field
    await message.answer(
        "What is the total amount of the claim? (Just enter the number, e.g., 120.50)"
    )
    await state.set_state(UserStates.claim_amount)

@router.message(UserStates.claim_amount)
async def handle_claim_amount(message: Message, state: FSMContext) -> None:
    """Process claim amount entry"""
    try:
        # Remove any currency symbols and commas
        amount_text = message.text.strip().replace("$", "").replace(",", "")
        amount = float(amount_text)
        await state.update_data(amount=amount)
        
        # Move to next field
        await message.answer(
            "Please provide a brief description of the service or treatment:"
        )
        await state.set_state(UserStates.claim_description)
    except ValueError:
        await message.answer(
            "Please provide a valid amount (e.g., 120.50):"
        )

@router.message(UserStates.claim_description)
async def handle_claim_description(message: Message, state: FSMContext) -> None:
    """Process claim description entry"""
    description = message.text.strip()
    if not description:
        await message.answer("Please provide a description:")
        return
        
    await state.update_data(description=description)
    
    # All fields collected, show summary and confirm
    user_data = await state.get_data()
    
    summary = (
        f"📋 Claim Summary:\n\n"
        f"Type: {user_data.get('claim_type')}\n"
        f"Date: {user_data.get('service_date')}\n"
        f"Provider: {user_data.get('provider_name')}\n"
        f"Amount: ${user_data.get('amount', 0):.2f}\n"
        f"Description: {user_data.get('description')}\n\n"
        f"Is this information correct?"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="✅ Submit Claim", callback_data="confirm_claim")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back_to_menu")]
    ]
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(summary, reply_markup=keyboard_markup)
    
    # Set state to reviewing claim
    await state.set_state(UserStates.reviewing_claim)

# Add handler for claim confirmation
@router.callback_query(lambda c: c.data == "confirm_claim")
async def confirm_claim_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle claim confirmation"""
    user_data = await state.get_data()
    policy_id = user_data.get("selected_policy_id")
    
    await callback_query.answer()
    
    processing_message = await callback_query.message.answer("Creating your claim...")
    
    try:
        # Create the claim data
        claim_data = {
            "policy_id": policy_id,
            "claim_type": user_data.get("claim_type"),
            "service_date": user_data.get("service_date"),
            "provider_name": user_data.get("provider_name"),
            "amount": user_data.get("amount", 0),
            "description": user_data.get("description"),
            "status": "pending"
        }
        
        # Save the claim
        created_claim = await db.create_claim(callback_query.from_user.id, claim_data)
        
        if not created_claim:
            raise ValueError("Failed to create claim")
        
        # Generate a claim form
        form_path = await claim_service.generate_claim_form(
            callback_query.from_user.id, 
            policy_id, 
            claim_data
        )
        
        # Delete processing message
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=processing_message.message_id)
        
        # Send a success message
        await callback_query.message.answer(
            f"✅ Your claim has been created successfully!\n\n"
            f"Claim Type: {claim_data['claim_type']}\n"
            f"Provider: {claim_data['provider_name']}\n"
            f"Amount: ${claim_data['amount']:.2f}\n"
            f"Status: Pending\n\n"
            f"You can track the status of your claim using the 'Track Claims' option."
        )
        
        # Send the claim form if it was generated
        if form_path:
            await callback_query.message.answer("Here's your completed claim form:")
            await callback_query.message.answer_document(FSInputFile(form_path))
            
            # Clean up the file
            try:
                form_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting claim form file {form_path}: {e}")
        
        # Return to main menu
        await callback_query.message.answer(
            "What would you like to do next?",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)
        
    except Exception as e:
        logger.error(f"Error creating claim: {e}")
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=processing_message.message_id)
        await callback_query.message.answer(
            "I couldn't process your claim. Please try again later.",
            reply_markup=await get_main_menu_keyboard()
        )
        await state.set_state(UserStates.main_menu)

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
    
    # Get policy provider and type
    provider = policy.get('provider', '')
    policy_type = policy.get('policy_type', 'Policy')
    
    # Get policy number from either policy_number or policy_id field
    policy_number = policy.get('policy_number', '')
    if not policy_number and 'policy_id' in policy:
        policy_number = policy['policy_id']
    
    # Format the policy details
    details = f"📋 Policy Details: {provider if provider else 'Unknown'} - {policy_type}\n\n"
    
    if policy_number:
        details += f"Policy Number: {policy_number}\n"
    
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
    elif "deductible" in policy:
        details += f"\nDeductible: {policy['deductible']}\n"
    
    if "out_of_pocket_max" in policy:
        details += f"Out-of-Pocket Maximum: {policy['out_of_pocket_max']}\n"
    elif "out_of_pocket_maximum" in policy:
        details += f"Out-of-Pocket Maximum: {policy['out_of_pocket_maximum']}\n"
    
    if "coverage_areas" in policy and policy["coverage_areas"]:
        details += "\n✅ Coverage Areas:\n"
        
        # Handle both dictionary and list formats for coverage areas
        if isinstance(policy["coverage_areas"], dict):
            for area, details_info in policy["coverage_areas"].items():
                if isinstance(details_info, dict):
                    limit = details_info.get("limit", "Not specified")
                else:
                    limit = details_info
                details += f"- {area}: {limit}\n"
        elif isinstance(policy["coverage_areas"], list):
            for area in policy["coverage_areas"]:
                if isinstance(area, dict):
                    coverage_type = area.get("coverage_type", "Unknown")
                    limit = area.get("limit", "Not specified")
                    details += f"- {coverage_type}: {limit}\n"
    
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
    
    # Get provider information from multiple possible sources
    provider_name = claim.get('provider_name', '')
    if not provider_name:
        provider_name = claim.get('provider', '')
    if not provider_name and policy:
        provider_name = policy.get('provider', '')
        if not provider_name:
            provider_name = policy.get('company', '')
        if not provider_name:
            provider_name = policy.get('policy_provider', '')
    
    policy_name = provider_name if provider_name else "Unknown"
    
    # Format the claim details
    details = f"📝 Claim Details\n\n"
    details += f"Type: {claim.get('claim_type', 'Unknown')}\n"
    details += f"Provider: {provider_name if provider_name else 'Unknown'}\n"
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

# Add profile management handler
@router.callback_query(lambda c: c.data == "my_profile")
async def my_profile_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the my profile button"""
    user_id = callback_query.from_user.id
    await callback_query.answer()
    await show_profile(callback_query, user_id, state)

# Helper function to show user profile
async def show_profile(message: Union[Message, CallbackQuery], user_id: int, state: FSMContext) -> None:
    """Show the user profile information"""
    # Get user details
    user = await db.get_user(user_id)
    
    if not user:
        if isinstance(message, CallbackQuery):
            await message.message.answer(
                "Error retrieving your profile information. Please try again later.",
                reply_markup=await get_main_menu_keyboard()
            )
        else:
            await message.answer(
                "Error retrieving your profile information. Please try again later.",
                reply_markup=await get_main_menu_keyboard()
            )
        await state.set_state(UserStates.main_menu)
        return
    
    # Display user profile
    profile_text = "👤 Your Profile Information:\n\n"
    
    # Basic information
    full_name = user.get("full_name", "")
    if not full_name:
        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        if first_name or last_name:
            full_name = f"{first_name} {last_name}".strip()
        else:
            full_name = user.get("username", "Not set")
    
    profile_text += f"Name: {full_name}\n"
    profile_text += f"Username: @{user.get('username', 'Not set')}\n"
    profile_text += f"Email: {user.get('email', 'Not set')}\n"
    profile_text += f"Phone: {user.get('phone', 'Not set')}\n"
    
    # Create keyboard for profile management options
    keyboard = [
        [InlineKeyboardButton(text="✏️ Update Name", callback_data="update_name")],
        [InlineKeyboardButton(text="✏️ Update Email", callback_data="update_email")],
        [InlineKeyboardButton(text="✏️ Update Phone", callback_data="update_phone")],
        [InlineKeyboardButton(text="← Back to Menu", callback_data="back_to_menu")]
    ]
    profile_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if isinstance(message, CallbackQuery):
        await message.message.answer(profile_text, reply_markup=profile_markup)
    else:
        await message.answer(profile_text, reply_markup=profile_markup)

# Add update name handler
@router.callback_query(lambda c: c.data == "update_name")
async def update_name_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the update name button"""
    await callback_query.answer()
    await callback_query.message.answer("Please enter your full name (first and last name):")
    await state.set_state(UserStates.entering_name)
    # Flag that we're coming from profile page, not initial setup
    await state.update_data(continue_to="profile_update")

# Add update email handler
@router.callback_query(lambda c: c.data == "update_email")
async def update_email_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the update email button"""
    await callback_query.answer()
    await callback_query.message.answer("Please enter your new email address:")
    await state.set_state(UserStates.entering_email)
    # Flag that we're coming from profile page
    await state.update_data(continue_to="profile_update")

# Add update phone handler
@router.callback_query(lambda c: c.data == "update_phone")
async def update_phone_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle the update phone button"""
    await callback_query.answer()
    await callback_query.message.answer("Please enter your new phone number:")
    await state.set_state(UserStates.entering_phone)
    # Flag that we're coming from profile page
    await state.update_data(continue_to="profile_update")

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
