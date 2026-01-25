from langchain_groq import ChatGroq
from src.config import GROQ_API_KEY

def get_llm():
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.2
    )
