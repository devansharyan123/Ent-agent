import os
import re
import logging
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from backend.database.models import Document, DocumentChunk, RagEmbedding

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DEVICE = "cpu"
CHUNK_CHAR_SIZE = 1000
_embedder: Optional[SentenceTransformer] = None


def get_embedder() -> SentenceTransformer:
    """Load embedding model with caching and error handling."""
    global _embedder
    if _embedder is None:
        try:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL} on device: {EMBEDDING_DEVICE}")
            _embedder = SentenceTransformer(
                EMBEDDING_MODEL,
                device=EMBEDDING_DEVICE,
                cache_folder=os.path.expanduser("~/.cache/sentence-transformers")
            )
            logger.info("✅ Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load embedding model: {str(e)}")
            raise RuntimeError(f"Embedding service failed: {str(e)}")
    return _embedder


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, max_chars: int = CHUNK_CHAR_SIZE) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: List[str] = []
    buffer = ""

    for paragraph in paragraphs:
        candidate = paragraph if not buffer else f"{buffer}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(buffer)
            buffer = ""

        if len(paragraph) <= max_chars:
            buffer = paragraph
            continue

        for start in range(0, len(paragraph), max_chars):
            chunks.append(paragraph[start:start + max_chars])

    if buffer:
        chunks.append(buffer)

    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts with error handling."""
    if not texts:
        return []

    try:
        embedder = get_embedder()
        embeddings = embedder.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            batch_size=32
        )
        logger.info(f"✅ Generated {len(embeddings)} embeddings")
        return [vector.tolist() for vector in embeddings]
    except Exception as e:
        logger.error(f"❌ Embedding failed: {str(e)}")
        raise


def get_or_create_document(db: Session, file_path: str, category: str) -> Document:
    document = db.query(Document).filter(Document.file_path == file_path).first()
    if document:
        return document

    document = Document(
        file_name=os.path.basename(file_path),
        file_path=file_path,
        category=category
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def clear_document_chunks(db: Session, document_id) -> None:
    chunk_ids = [row[0] for row in db.query(DocumentChunk.id).filter(DocumentChunk.document_id == document_id).all()]
    if chunk_ids:
        db.query(RagEmbedding).filter(RagEmbedding.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(synchronize_session=False)
        db.commit()


def persist_document_chunks(db: Session, document: Document, chunks: List[str], embeddings: List[List[float]]) -> int:
    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings length mismatch")

    count = 0
    for index, chunk_text in enumerate(chunks):
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            chunk_text=chunk_text
        )
        db.add(chunk)
        db.flush()

        embedding = RagEmbedding(
            chunk_id=chunk.id,
            embedding=embeddings[index],
            embedding_model=EMBEDDING_MODEL
        )
        db.add(embedding)
        count += 1

    db.commit()
    return count


def ingest_policy_pdfs(db: Session, policies_root: Optional[str] = None) -> int:
    if policies_root is None:
        base_dir = Path(__file__).resolve().parents[1]
        policies_root = str(base_dir.parent / "storage" / "policies")

    root = Path(policies_root)
    if not root.exists():
        raise FileNotFoundError(f"Policies folder not found: {root}")

    total_chunks = 0
    for category in ["general", "hr", "admin"]:
        category_dir = root / category
        if not category_dir.exists():
            continue

        for file_path in sorted(category_dir.iterdir()):
            if not file_path.is_file():
                continue

            text = extract_text(file_path)
            if not text.strip():
                continue

            chunks = chunk_text(text)
            if not chunks:
                continue

            document = get_or_create_document(db, str(file_path.resolve()), category)
            clear_document_chunks(db, document.id)

            embeddings = embed_texts(chunks)
            written = persist_document_chunks(db, document, chunks, embeddings)
            total_chunks += written

    return total_chunks
