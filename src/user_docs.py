# src/user_docs.py
"""
Per-user document RAG pipeline.

Flow:
  upload_document()  → load bytes → chunk (500 chars, 50 overlap)
                     → embed → FAISS index saved per user
  user_rag_ask()     → embed query → top-k retrieval → LLM answer + citations
  get_user_documents() → returns metadata dict from manifest
  delete_document()  → removes chunks + manifest entry + rebuilds index
"""

import os
import io
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("atom.user_docs")

# ── Storage root ──────────────────────────────────────────────────────────────
USER_DOCS_ROOT = os.environ.get("USER_DOCS_ROOT", "user_data/docs")


# ═════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _user_dir(username: str) -> str:
    d = os.path.join(USER_DOCS_ROOT, username)
    os.makedirs(d, exist_ok=True)
    return d


def _manifest_path(username: str) -> str:
    return os.path.join(_user_dir(username), "manifest.json")


def _index_dir(username: str) -> str:
    d = os.path.join(_user_dir(username), "faiss_index")
    os.makedirs(d, exist_ok=True)
    return d


def _load_manifest(username: str) -> Dict[str, Any]:
    path = _manifest_path(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(username: str, manifest: Dict[str, Any]):
    with open(_manifest_path(username), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _get_embeddings():
    """Return HuggingFace embeddings (local, no API key needed)."""
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _get_text_splitter(chunk_size: int = 500, chunk_overlap: int = 50):
    """
    Import RecursiveCharacterTextSplitter from whichever langchain
    package is installed. Handles both old and new package layouts:
      - langchain_text_splitters  (langchain >= 0.2)
      - langchain.text_splitter   (langchain < 0.2, legacy)
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
        except ImportError:
            raise ImportError(
                "Could not import RecursiveCharacterTextSplitter. "
                "Please run:  pip install langchain-text-splitters"
            )

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _chunk_documents(docs: list, chunk_size: int = 500, chunk_overlap: int = 50) -> list:
    """Split LangChain Document objects into smaller chunks."""
    splitter = _get_text_splitter(chunk_size, chunk_overlap)
    chunks   = splitter.split_documents(docs)
    logger.info(f"Chunking: {len(docs)} pages → {len(chunks)} chunks")
    return chunks


def _load_user_vectorstore(username: str):
    """Load existing FAISS index for a user, or return None."""
    from langchain_community.vectorstores import FAISS

    idx_dir    = _index_dir(username)
    index_file = os.path.join(idx_dir, "index.faiss")
    if not os.path.exists(index_file):
        return None

    embeddings = _get_embeddings()
    return FAISS.load_local(idx_dir, embeddings, allow_dangerous_deserialization=True)


def _save_user_vectorstore(username: str, vectorstore):
    """Persist FAISS index to disk."""
    vectorstore.save_local(_index_dir(username))


def _drop_chunks_for_file(vectorstore, filename: str, embeddings):
    """
    Rebuild FAISS index without chunks belonging to `filename`.
    (FAISS has no targeted delete, so we reconstruct from remaining docs.)
    """
    from langchain_community.vectorstores import FAISS

    all_docs = list(vectorstore.docstore._dict.values())
    kept     = [d for d in all_docs if d.metadata.get("filename") != filename]

    if not kept:
        return None  # caller will create fresh index

    return FAISS.from_documents(kept, embeddings)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════

def upload_document(username: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Index an uploaded document into the user's personal FAISS store.

    Steps:
      1. Parse file → LangChain Documents  (via doc_loader)
      2. Chunk each page into ~500-char pieces with 50-char overlap
      3. Embed and upsert into user's FAISS index (merges with existing)
      4. Update manifest
    """
    try:
        from langchain_community.vectorstores import FAISS
        from src.tools.doc_loader import load_uploaded_file

        # ── 1. Parse ──────────────────────────────────────────────────────
        raw_docs = load_uploaded_file(file_bytes, filename, username)
        if not raw_docs:
            return {
                "success":  False,
                "filename": filename,
                "pages":    0,
                "chunks":   0,
                "message":  (
                    "No text could be extracted from the file. "
                    "It may be a scanned image PDF — try OCR first."
                ),
            }

        num_pages = len(raw_docs)

        # ── 2. Chunk ──────────────────────────────────────────────────────
        chunks = _chunk_documents(raw_docs, chunk_size=500, chunk_overlap=50)

        # Tag every chunk with filename for later deletion
        for chunk in chunks:
            chunk.metadata["filename"] = filename

        num_chunks = len(chunks)

        # ── 3. Embed + upsert ─────────────────────────────────────────────
        embeddings = _get_embeddings()
        existing   = _load_user_vectorstore(username)

        if existing is None:
            vs = FAISS.from_documents(chunks, embeddings)
        else:
            # Drop stale chunks for this file (handles re-upload)
            existing = _drop_chunks_for_file(existing, filename, embeddings)
            if existing is None:
                vs = FAISS.from_documents(chunks, embeddings)
            else:
                new_vs = FAISS.from_documents(chunks, embeddings)
                existing.merge_from(new_vs)
                vs = existing

        _save_user_vectorstore(username, vs)

        # ── 4. Manifest ───────────────────────────────────────────────────
        manifest           = _load_manifest(username)
        manifest[filename] = {
            "filename":    filename,
            "file_type":   Path(filename).suffix.lstrip(".").lower(),
            "pages":       num_pages,
            "chunks":      num_chunks,
            "size_kb":     round(len(file_bytes) / 1024, 1),
            "uploaded_at": datetime.utcnow().isoformat(),
        }
        _save_manifest(username, manifest)

        logger.info(
            f"[UserDocs] '{filename}' for '{username}': "
            f"{num_pages} pages, {num_chunks} chunks indexed."
        )
        return {
            "success":  True,
            "filename": filename,
            "pages":    num_pages,
            "chunks":   num_chunks,
            "message":  "Indexed successfully.",
        }

    except Exception as e:
        logger.exception(f"[UserDocs] upload_document failed for '{filename}': {e}")
        return {
            "success":  False,
            "filename": filename,
            "pages":    0,
            "chunks":   0,
            "message":  str(e),
        }


def get_user_documents(username: str) -> Dict[str, Any]:
    """Return the manifest dict: { filename → metadata }."""
    return _load_manifest(username)


def delete_document(username: str, filename: str) -> Dict[str, Any]:
    """Remove a document's chunks from the index and update the manifest."""
    try:
        manifest = _load_manifest(username)
        if filename not in manifest:
            return {
                "success": False,
                "message": f"'{filename}' not found in your documents.",
            }

        embeddings = _get_embeddings()
        existing   = _load_user_vectorstore(username)

        if existing is not None:
            updated = _drop_chunks_for_file(existing, filename, embeddings)
            if updated is not None:
                _save_user_vectorstore(username, updated)
            else:
                import shutil
                shutil.rmtree(_index_dir(username), ignore_errors=True)

        del manifest[filename]
        _save_manifest(username, manifest)

        return {"success": True, "message": f"'{filename}' deleted."}

    except Exception as e:
        logger.exception(f"[UserDocs] delete_document failed: {e}")
        return {"success": False, "message": str(e)}


def user_rag_ask(
    username:     str,
    question:     str,
    chat_history: List[Dict[str, str]],
    top_k:        int = 6,
) -> Dict[str, Any]:
    """
    RAG Q&A over the user's personal document store.

    Steps:
      1. Load user's FAISS index
      2. Retrieve top_k most relevant chunks
      3. Build prompt with numbered context + recent chat history
      4. Call LLM → return answer + structured source citations
    """
    try:
        vs = _load_user_vectorstore(username)

        if vs is None:
            return {
                "answer":  (
                    "You haven't uploaded any documents yet. "
                    "Please upload a PDF, Word doc, or text file first."
                ),
                "sources": [],
            }

        # ── 1. Retrieve relevant chunks ───────────────────────────────────
        retriever = vs.as_retriever(
            search_type="similarity",
            search_kwargs={"k": top_k},
        )
        chunks = retriever.invoke(question)

        if not chunks:
            return {
                "answer":  (
                    "I couldn't find relevant content in your documents "
                    "for that question. Try rephrasing or uploading more material."
                ),
                "sources": [],
            }

        # ── 2. Build numbered context string ──────────────────────────────
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            fname = chunk.metadata.get("filename", chunk.metadata.get("source", "Unknown"))
            page  = chunk.metadata.get("page", "?")
            text  = chunk.page_content.strip()
            context_parts.append(f"[{i}] File: {fname} | Page: {page}\n{text}")

        context = "\n\n---\n\n".join(context_parts)

        # ── 3. Recent chat history (last 6 turns) ─────────────────────────
        recent   = chat_history[-6:] if len(chat_history) > 6 else chat_history
        hist_txt = ""
        for msg in recent:
            role     = "User" if msg["role"] == "user" else "Assistant"
            hist_txt += f"{role}: {msg.get('content', '')}\n"

        # ── 4. Prompt ─────────────────────────────────────────────────────
        prompt = f"""You are a helpful document assistant. Answer the user's question
STRICTLY using the provided document excerpts below. Do not use outside knowledge.

Instructions:
- Give a clear, structured answer using headings and bullet points where helpful.
- Cite sources inline as [1], [2], etc., matching the excerpt numbers above.
- If the answer is not in the documents, say so clearly instead of guessing.

--- DOCUMENT EXCERPTS ---
{context}

--- RECENT CONVERSATION ---
{hist_txt}--- END ---

User Question: {question}

Answer:"""

        # ── 5. Call LLM ───────────────────────────────────────────────────
        from src.llm import get_llm
        llm      = get_llm()
        response = llm.invoke(prompt)
        answer   = response.content.strip()

        # ── 6. Build deduplicated source citations ────────────────────────
        sources = []
        seen    = set()
        for chunk in chunks:
            fname  = chunk.metadata.get("filename", chunk.metadata.get("source", "Unknown"))
            page   = chunk.metadata.get("page", "?")
            key    = (fname, page)
            if key in seen:
                continue
            seen.add(key)
            excerpt = chunk.page_content.strip()[:200].replace("\n", " ")
            sources.append({"filename": fname, "page": page, "excerpt": excerpt})

        logger.info(
            f"[UserDocs] Q&A for '{username}': "
            f"{len(chunks)} chunks retrieved, {len(sources)} unique sources."
        )
        return {"answer": answer, "sources": sources}

    except Exception as e:
        logger.exception(f"[UserDocs] user_rag_ask failed: {e}")
        return {
            "answer":  f"⚠️ An error occurred while searching your documents: {e}",
            "sources": [],
        }