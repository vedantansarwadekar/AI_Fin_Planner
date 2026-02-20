"""
LLM utilities for all agents using LangChain
Provides unified interface for Groq via LangChain
"""

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.config import GROQ_API_KEY


def get_llm(temperature=0.2, model="llama-3.3-70b-versatile"):
    """
    Get LangChain ChatGroq instance
    
    Args:
        temperature (float): Response creativity (0-1)
        model (str): Groq model name
        
    Returns:
        ChatGroq: Configured LangChain LLM instance
        
    Usage:
        llm = get_llm()
        response = llm.invoke("What is Python?")
    """
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model=model,
        temperature=temperature
    )


def get_llm_response(prompt, system_message=None, temperature=0.2):
    """
    Get simple LLM response (no history)
    
    Args:
        prompt (str): User's question/input
        system_message (str, optional): System prompt to set behavior
        temperature (float): Response creativity
        
    Returns:
        str: LLM's response text
        
    Usage:
        # Simple usage
        response = get_llm_response("What is a list in Python?")
        
        # With system message
        response = get_llm_response(
            prompt="Explain this error",
            system_message="You are a Python tutor"
        )
    """
    try:
        llm = get_llm(temperature=temperature)
        messages = []
        
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        messages.append(HumanMessage(content=prompt))
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        return f"Error getting LLM response: {str(e)}"


def get_llm_response_with_history(prompt, chat_history, system_message=None, temperature=0.2):
    """
    Get LLM response with conversation history
    
    Args:
        prompt (str): Current user input
        chat_history (list): Previous conversation messages
            Format: [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
            ]
        system_message (str, optional): System prompt
        temperature (float): Response creativity
        
    Returns:
        str: LLM's response text
        
    Usage:
        history = [
            {"role": "user", "content": "What is a variable?"},
            {"role": "assistant", "content": "A variable is..."}
        ]
        response = get_llm_response_with_history(
            prompt="Can you give an example?",
            chat_history=history,
            system_message="You are a Python tutor"
        )
    """
    try:
        llm = get_llm(temperature=temperature)
        messages = []
        
        # Add system message
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        # Convert chat history to LangChain format
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # Add current prompt
        messages.append(HumanMessage(content=prompt))
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        return f"Error getting LLM response: {str(e)}"