
import os
from functools import lru_cache
from uuid import UUID, uuid5

import fitz
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "document_chunks")
MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
)

CHUNK_WORDS = 200
OVERLAP_WORDS = 40


@lru_cache(maxsize=1)
def embedding_model():
    return TextEmbedding(model_name=MODEL_NAME)


def extract_pages(pdf_bytes: bytes):
    pages = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()

            if text:
                pages.append({
                    "page_number": number,
                    "text": text,
                })

    return pages


def chunk_pages(pages):
    chunks = []
    step = CHUNK_WORDS - OVERLAP_WORDS

    for page in pages:
        words = page["text"].split()

        for start in range(0, len(words), step):
            chunk_words = words[start:start + CHUNK_WORDS]

            if not chunk_words:
                continue

            chunks.append({
                "page_number": page["page_number"],
                "chunk_index": len(chunks),
                "text": " ".join(chunk_words),
            })

            if start + CHUNK_WORDS >= len(words):
                break

    return chunks


def index_pdf(
    document_id: UUID,
    filename: str,
    pdf_bytes: bytes,
):
    pages = extract_pages(pdf_bytes)
    chunks = chunk_pages(pages)

    if not chunks:
        raise ValueError(
            "No extractable text found in this PDF"
        )

    model = embedding_model()

    vectors = list(
        model.embed(chunk["text"] for chunk in chunks)
    )

    client = QdrantClient(url=QDRANT_URL, timeout=60)

    try:
        vector_size = len(vectors[0])

        if not client.collection_exists(COLLECTION):
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

        points = []

        for chunk, vector in zip(chunks, vectors):
            point_id = str(
                uuid5(
                    document_id,
                    str(chunk["chunk_index"]),
                )
            )

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "document_id": str(document_id),
                        "filename": filename,
                        "page_number": chunk["page_number"],
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                    },
                )
            )

        # Remove existing chunks when reprocessing.
        client.delete(
            collection_name=COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=str(document_id)
                            ),
                        )
                    ]
                )
            ),
            wait=True,
        )

        # Upload in batches rather than one huge request.
        for start in range(0, len(points), 64):
            client.upsert(
                collection_name=COLLECTION,
                points=points[start:start + 64],
                wait=True,
            )

        return {
            "document_id": str(document_id),
            "status": "completed",
            "pages_processed": len(pages),
            "chunks_created": len(chunks),
            "vectors_stored": len(points),
        }

    finally:
        client.close()

