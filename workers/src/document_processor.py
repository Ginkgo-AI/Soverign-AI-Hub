"""Background document processing worker.

Listens to Redis Streams for document processing jobs.
Pipeline: parse -> chunk -> embed -> store in Qdrant + PostgreSQL.
"""

import json
import logging
import os
import sys
import time
import uuid

import httpx
import redis

# ── Configuration ──────────────────────────────────────────────────────

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
STREAM_NAME = "document_jobs"
CONSUMER_GROUP = "doc_processors"
CONSUMER_NAME = f"worker-{os.getpid()}"

GATEWAY_HOST = os.environ.get("GATEWAY_HOST", "localhost")
GATEWAY_PORT = os.environ.get("GATEWAY_PORT", "8888")
GATEWAY_BASE = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}"

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

VLLM_HOST = os.environ.get("VLLM_HOST", "vllm")
VLLM_PORT = int(os.environ.get("VLLM_PORT", "8000"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

POSTGRES_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://sovereign:changeme_in_production@localhost:5432/sovereign_ai",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("document_processor")

# ── Lazy imports of heavy dependencies ─────────────────────────────────

_sqlalchemy_ready = False
_Session = None
_Chunk = None
_Document = None


def _init_sqlalchemy():
    global _sqlalchemy_ready, _Session, _Chunk, _Document
    if _sqlalchemy_ready:
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

    # Import the models — we need to add the project path for this worker
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gateway"))
    from app.models.collection import Chunk, Document

    _Session = sessionmaker(bind=engine)
    _Chunk = Chunk
    _Document = Document
    _sqlalchemy_ready = True


def _init_qdrant():
    from qdrant_client import QdrantClient

    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60)


# ── Document pipeline functions ────────────────────────────────────────

def parse_document(file_path: str, filename: str) -> list[dict]:
    """Parse a file into pages of {text, metadata}."""
    # Reuse the gateway pipeline parser (sync wrapper)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gateway"))
    from app.services.document_pipeline import parse_document as _async_parse

    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_async_parse(file_path, filename))
    finally:
        loop.close()


def chunk_pages(pages: list[dict], chunk_size: int = 512, chunk_overlap: int = 50) -> list[dict]:
    """Chunk pages into smaller pieces."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gateway"))
    from app.services.document_pipeline import chunk_pages as _chunk_pages

    return _chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Call the vLLM embedding endpoint synchronously."""
    if not texts:
        return []

    url = f"http://{VLLM_HOST}:{VLLM_PORT}/v1/embeddings"
    all_embeddings: list[list[float]] = []
    batch_size = 64

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        payload = {"input": batch, "model": EMBEDDING_MODEL}

        response = httpx.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json().get("data", [])

        # Sort by index
        data.sort(key=lambda d: d.get("index", 0))
        all_embeddings.extend([d["embedding"] for d in data])

    return all_embeddings


def store_in_qdrant(
    qdrant_client,
    collection_id: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    document_id: str,
    filename: str,
):
    """Store vectors in Qdrant."""
    from qdrant_client.models import PointStruct

    col_name = f"col_{collection_id.replace('-', '_')}"

    points = []
    for chunk, embedding in zip(chunks, embeddings):
        point_id = str(uuid.uuid4())
        meta = chunk.get("metadata", {})
        payload = {
            "content": chunk["text"],
            "document_id": document_id,
            "document_name": filename,
            "collection_id": collection_id,
            "chunk_index": meta.get("chunk_index", 0),
            "page_number": meta.get("page_number"),
        }
        points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        # Save point ID back for PostgreSQL storage
        chunk["_point_id"] = point_id

    # Batch upsert
    batch_size = 100
    for start in range(0, len(points), batch_size):
        batch = points[start : start + batch_size]
        qdrant_client.upsert(collection_name=col_name, points=batch)

    logger.info("Stored %d vectors in Qdrant collection '%s'", len(points), col_name)


def store_in_postgres(
    document_id: str,
    chunks: list[dict],
    filename: str,
):
    """Store chunk records in PostgreSQL."""
    _init_sqlalchemy()
    session = _Session()

    try:
        # Update document status
        doc = session.query(_Document).filter_by(id=uuid.UUID(document_id)).first()
        if doc:
            doc.status = "processing"
            doc.chunk_count = len(chunks)
            session.flush()

        # Insert chunks
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            db_chunk = _Chunk(
                id=uuid.uuid4(),
                document_id=uuid.UUID(document_id),
                content=chunk["text"],
                chunk_index=meta.get("chunk_index", 0),
                page_number=meta.get("page_number"),
                embedding_id=chunk.get("_point_id"),
                metadata_=meta,
            )
            session.add(db_chunk)

        # Mark document as ready
        if doc:
            doc.status = "ready"

        session.commit()
        logger.info("Stored %d chunks in PostgreSQL for document %s", len(chunks), document_id)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_document_status(document_id: str, status: str, error_message: str | None = None):
    """Update the document status in PostgreSQL."""
    _init_sqlalchemy()
    session = _Session()
    try:
        doc = session.query(_Document).filter_by(id=uuid.UUID(document_id)).first()
        if doc:
            doc.status = status
            if error_message:
                doc.metadata_ = {**(doc.metadata_ or {}), "error": error_message}
            session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to update document status for %s", document_id)
    finally:
        session.close()


# ── Main processing function ──────────────────────────────────────────

def process_document(job_data: dict) -> None:
    """Process a single document through the full ingestion pipeline."""
    document_id = job_data.get("document_id")
    file_path = job_data.get("file_path")
    collection_id = job_data.get("collection_id")
    filename = job_data.get("filename", "unknown")
    chunk_size = int(job_data.get("chunk_size", 512))
    chunk_overlap = int(job_data.get("chunk_overlap", 50))

    logger.info("Processing document %s: %s (collection: %s)", document_id, filename, collection_id)

    try:
        # Step 1: Parse document
        logger.info("[1/4] Parsing: %s", filename)
        update_document_status(document_id, "processing")
        pages = parse_document(file_path, filename)
        logger.info("  Parsed %d pages from %s", len(pages), filename)

        # Step 2: Chunk text
        logger.info("[2/4] Chunking: size=%d, overlap=%d", chunk_size, chunk_overlap)
        chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        logger.info("  Created %d chunks", len(chunks))

        if not chunks:
            raise ValueError(f"No chunks produced from {filename}")

        # Step 3: Generate embeddings
        logger.info("[3/4] Generating embeddings for %d chunks", len(chunks))
        texts = [c["text"] for c in chunks]
        embeddings = generate_embeddings(texts)
        logger.info("  Generated %d embeddings (dim=%d)", len(embeddings), len(embeddings[0]) if embeddings else 0)

        # Step 4: Store in Qdrant + PostgreSQL
        logger.info("[4/4] Storing in Qdrant + PostgreSQL")
        qdrant = _init_qdrant()

        store_in_qdrant(qdrant, collection_id, chunks, embeddings, document_id, filename)
        store_in_postgres(document_id, chunks, filename)

        # Clean up temp file
        try:
            os.remove(file_path)
            logger.info("Cleaned up temp file: %s", file_path)
        except OSError:
            logger.warning("Failed to clean up temp file: %s", file_path)

        logger.info("Document %s processed successfully: %d chunks", document_id, len(chunks))

    except Exception as e:
        logger.exception("Failed to process document %s", document_id)
        update_document_status(document_id, "error", str(e))


# ── Redis consumer loop ───────────────────────────────────────────────

def main():
    logger.info("Document processor worker starting (PID: %d)", os.getpid())

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Wait for Redis
    while True:
        try:
            r.ping()
            break
        except redis.ConnectionError:
            logger.info("Waiting for Redis at %s:%d ...", REDIS_HOST, REDIS_PORT)
            time.sleep(2)

    # Create consumer group if it doesn't exist
    try:
        r.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError:
        pass  # Group already exists

    logger.info("Listening on stream '%s' as '%s/%s'...", STREAM_NAME, CONSUMER_GROUP, CONSUMER_NAME)

    while True:
        try:
            messages = r.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_NAME: ">"},
                count=1,
                block=5000,
            )

            if not messages:
                continue

            for stream, entries in messages:
                for msg_id, data in entries:
                    try:
                        job = json.loads(data.get("payload", "{}"))
                        process_document(job)
                        r.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                    except Exception as e:
                        logger.error("Error processing message %s: %s", msg_id, e)

        except KeyboardInterrupt:
            logger.info("Shutting down worker...")
            break
        except Exception as e:
            logger.error("Worker error: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
