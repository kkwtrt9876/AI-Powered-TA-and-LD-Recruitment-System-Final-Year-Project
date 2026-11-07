from pathlib import Path
import os

from dotenv import load_dotenv
from groq import Groq

# Base directory of the project (rag_chatbot/)
BASE_DIR = Path(__file__).resolve().parents[1]

# Load .env
load_dotenv(BASE_DIR / ".env")

# Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

# Groq client + model
groq_client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "llama-3.3-70b-versatile"

# Data / Chroma paths
DATA_PATH = BASE_DIR / "data" / "Chatbot_Dataset.xlsx"  # or .csv if you prefer
CHROMA_DIR = BASE_DIR / "chroma_store"
CHROMA_COLLECTION = "chatbot_kb"

