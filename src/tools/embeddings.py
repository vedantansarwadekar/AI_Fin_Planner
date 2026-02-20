from langchain_community.embeddings import HuggingFaceEmbeddings


def get_embeddings():
    """
    Returns embedding model.
    """
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
