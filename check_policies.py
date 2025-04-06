import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.config import MONGODB_URI, DB_NAME

async def check_policies():
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # Get all policies
    policies = await db.policies.find().to_list(length=None)
    
    print(f"Found {len(policies)} policies:")
    for policy in policies:
        print(f"\nPolicy ID: {policy['_id']}")
        print(f"Provider: {policy['provider']}")
        print(f"Policy Number: {policy['policy_number']}")
        print(f"Coverage Areas: {list(policy['coverage_areas'].keys())}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check_policies()) 