import os
from typing import List, Dict, Any
from datetime import datetime

from src.tools.pdf_loader import load_pdfs
from src.tools.text_splitter import split_documents
from src.tools.vector_store import (
    build_faiss_index,
    load_faiss_index,
    VECTOR_DB_PATH,
)
from src.llm import get_llm




class StockMarketRAGAgent:
    """
    Stock Market RAG Agent using RBI & SEBI documents.
    Now supports feedback logging.
    """

    def __init__(self):
        self.llm = get_llm()
        self.vector_db = None



    # ---------------------------------------------------
    # PDF INGESTION
    # ---------------------------------------------------
    def ingest_pdfs(self, pdf_paths: List[str]):
        if os.path.exists(VECTOR_DB_PATH):
            self.vector_db = load_faiss_index()
            return {"status": "loaded_existing_index"}

        docs = load_pdfs(pdf_paths)
        chunks = split_documents(docs)
        self.vector_db = build_faiss_index(chunks)

        return {
            "status": "built_new_index",
            "pdfs_loaded": len(pdf_paths),
            "chunks_created": len(chunks),
        }

    # ---------------------------------------------------
    # MAIN ASK METHOD
    # ---------------------------------------------------
    def ask(self, query: str, answer_style: str = "Detailed"):

        if not self.vector_db:
            self.vector_db = load_faiss_index()

        retriever = self.vector_db.as_retriever(search_kwargs={"k": 6})
        docs = retriever.invoke(query)

        context_blocks = []
        for doc in docs:
            source = os.path.basename(doc.metadata.get("source", "Unknown"))
            page = doc.metadata.get("page", "N/A")
            content = doc.page_content.strip()

            context_blocks.append(
                f"Source: {source} | Page: {page}\n{content}"
            )

        context = "\n\n---\n\n".join(context_blocks)

        if answer_style == "Concise":
            instructions = """
- Give a SHORT and PRECISE answer.
- Use bullet points only.
- Mention sections only if clearly present.
- Do not over-explain.
"""
        else:
            instructions = """
- Give a DETAILED and STRUCTURED answer.
- Use headings and numbered/bulleted lists.
- Explicitly mention sections and clauses if present.
- Include inline citations like (SEBI Act, 1992 – Page 21).
"""

        prompt = f"""
You are a financial and regulatory law expert.

Answer STRICTLY using the context below.
Do NOT use external knowledge.

Instructions:
{instructions}

Context:
{context}

Question:
{query}

Answer:
"""

        response = self.llm.invoke(prompt)
        answer_text = response.content

        sources = [
            {
                "source": os.path.basename(doc.metadata.get("source", "Unknown")),
                "page": doc.metadata.get("page", "N/A"),
            }
            for doc in docs
        ]

        return {
            "answer": answer_text,
            "sources": sources,
        }
