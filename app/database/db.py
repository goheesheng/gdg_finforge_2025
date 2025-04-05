import motor.motor_asyncio
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional, Any, Union

from app.config.config import MONGODB_URI, DB_NAME

# Create a Motor client
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

# Collections
users_collection = db.users
policies_collection = db.policies
claims_collection = db.claims
chat_history_collection = db.chat_history

async def get_user(user_id: int) -> Optional[Dict]:
    """Get a user by Telegram user ID"""
    return await users_collection.find_one({"user_id": user_id})

async def create_user(user_data: Dict) -> Dict:
    """Create a new user"""
    user_data["created_at"] = datetime.utcnow()
    user_data["updated_at"] = datetime.utcnow()
    
    # Make sure user doesn't already exist
    existing_user = await get_user(user_data["user_id"])
    if existing_user:
        return existing_user
        
    result = await users_collection.insert_one(user_data)
    return await users_collection.find_one({"_id": result.inserted_id})

async def update_user(user_id: int, update_data: Dict) -> Optional[Dict]:
    """Update a user's information"""
    update_data["updated_at"] = datetime.utcnow()
    
    result = await users_collection.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count:
        return await get_user(user_id)
    return None

async def save_policy(user_id: int, policy_data: Dict) -> Dict:
    """Save a policy to the database"""
    policy_data["user_id"] = user_id
    policy_data["created_at"] = datetime.utcnow()
    policy_data["updated_at"] = datetime.utcnow()
    
    result = await policies_collection.insert_one(policy_data)
    return await policies_collection.find_one({"_id": result.inserted_id})

async def get_policies(user_id: int) -> List[Dict]:
    """Get all policies for a user"""
    cursor = policies_collection.find({"user_id": user_id})
    return await cursor.to_list(length=None)

async def get_policy(policy_id: Union[str, ObjectId]) -> Optional[Dict]:
    """Get a policy by ID"""
    if isinstance(policy_id, str):
        policy_id = ObjectId(policy_id)
    return await policies_collection.find_one({"_id": policy_id})

async def create_claim(user_id: int, claim_data: Dict) -> Dict:
    """Create a new claim"""
    claim_data["user_id"] = user_id
    claim_data["status"] = claim_data.get("status", "pending")
    claim_data["created_at"] = datetime.utcnow()
    claim_data["updated_at"] = datetime.utcnow()
    
    result = await claims_collection.insert_one(claim_data)
    return await claims_collection.find_one({"_id": result.inserted_id})

async def update_claim(claim_id: Union[str, ObjectId], update_data: Dict) -> Optional[Dict]:
    """Update a claim"""
    if isinstance(claim_id, str):
        claim_id = ObjectId(claim_id)
        
    update_data["updated_at"] = datetime.utcnow()
    
    result = await claims_collection.update_one(
        {"_id": claim_id},
        {"$set": update_data}
    )
    
    if result.modified_count:
        return await claims_collection.find_one({"_id": claim_id})
    return None

async def get_claims(user_id: int) -> List[Dict]:
    """Get all claims for a user"""
    cursor = claims_collection.find({"user_id": user_id})
    return await cursor.to_list(length=None)

async def get_claim(claim_id: Union[str, ObjectId]) -> Optional[Dict]:
    """Get a claim by ID"""
    if isinstance(claim_id, str):
        claim_id = ObjectId(claim_id)
    return await claims_collection.find_one({"_id": claim_id})

async def save_chat_message(user_id: int, message_data: Dict) -> Dict:
    """Save a chat message to history"""
    message_data["user_id"] = user_id
    message_data["timestamp"] = datetime.utcnow()
    
    result = await chat_history_collection.insert_one(message_data)
    return await chat_history_collection.find_one({"_id": result.inserted_id})

async def get_chat_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Get recent chat history for a user"""
    cursor = chat_history_collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=None)
