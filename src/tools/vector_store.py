import os
from langchain_community.vectorstores import FAISS
from src.tools.embeddings import get_embeddings


VECTOR_DB_PATH = "data/vector_store"


def build_faiss_index(documents):
    """
    Create FAISS vector store from documents.
    """
    embeddings = get_embeddings()
    db = FAISS.from_documents(documents, embeddings)
    db.save_local(VECTOR_DB_PATH)
    return db


def load_faiss_index():
    """
    Load FAISS vector store from disk.
    """
    embeddings = get_embeddings()
    return FAISS.load_local(
        VECTOR_DB_PATH,
        embeddings,
        allow_dangerous_deserialization=True
    )
