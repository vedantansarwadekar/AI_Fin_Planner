from typing import List
from langchain_community.document_loaders import PyPDFLoader


def load_pdfs(pdf_paths: List[str]):
    """
    Load PDFs and return LangChain Document objects.
    STEP 0 responsibility:
    - Load PDFs safely
    - Extract raw text
    - No embeddings, no vectors
    """

    documents = []

    for path in pdf_paths:
        loader = PyPDFLoader(path)
        docs = loader.load()
        documents.extend(docs)

    return documents
