from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# MongoDB Atlas URI from environment
MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB")

# Connect to MongoDB Atlas
client = AsyncIOMotorClient(MONGO_URI)

# Access database
db = client[DB_NAME]

# Optional: helper function to get collections
def get_collection(collection_name: str):
    return db[collection_name]
