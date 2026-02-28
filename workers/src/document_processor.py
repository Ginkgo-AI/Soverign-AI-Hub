"""Background document processing worker.

Listens to Redis Streams for document processing jobs.
Pipeline: parse -> chunk -> embed -> store in Qdrant.
"""

import json
import os
import time

import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
STREAM_NAME = "document_jobs"
CONSUMER_GROUP = "doc_processors"
CONSUMER_NAME = f"worker-{os.getpid()}"


def process_document(job_data: dict) -> None:
    """Process a single document through the ingestion pipeline."""
    document_id = job_data.get("document_id")
    file_path = job_data.get("file_path")
    collection_id = job_data.get("collection_id")

    print(f"Processing document {document_id}: {file_path}")

    # Phase 2 implementation:
    # 1. Parse document (PDF, DOCX, etc.)
    # 2. Chunk text (recursive, semantic, or structure-aware)
    # 3. Generate embeddings (local model)
    # 4. Store chunks in PostgreSQL + vectors in Qdrant
    # 5. Update document status to "ready"

    print(f"Document {document_id} processed (stub)")


def main():
    print(f"Document processor worker starting (PID: {os.getpid()})")

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Wait for Redis
    while True:
        try:
            r.ping()
            break
        except redis.ConnectionError:
            print("Waiting for Redis...")
            time.sleep(2)

    # Create consumer group if it doesn't exist
    try:
        r.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError:
        pass  # Group already exists

    print(f"Listening on stream '{STREAM_NAME}'...")

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
                        print(f"Error processing {msg_id}: {e}")

        except KeyboardInterrupt:
            print("Shutting down worker...")
            break
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
