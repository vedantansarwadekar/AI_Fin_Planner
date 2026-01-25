# src/tools/web_search.py

from langchain_tavily import TavilySearch

def web_search(query: str):
    """
    Search the web using Tavily.
    Returns top results as JSON.
    """
    tool = TavilySearch(max_results=5)
    return tool.invoke({"query": query})
