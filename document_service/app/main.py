
import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.rag import answer_document_question
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    DateTime, Integer, LargeBinary, String,
    create_engine, func, select
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session,
    mapped_column, sessionmaker
)
from app.processing import index_pdf

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ["DOCUMENT_API_KEY"]
MAX_FILE_SIZE = 10 * 1024 * 1024


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    file_data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    with SessionLocal() as session:
        yield session

def process_uploaded_document(document_id: UUID):
    with SessionLocal() as db:
        document = db.get(Document, document_id)

        if document is None:
            return

        index_pdf(
            document_id=document.id,
            filename=document.filename,
            pdf_bytes=document.file_data,
        )


def require_api_key(
    x_api_key: str | None = Header(default=None),
):
    if not API_KEY or not x_api_key or not hmac.compare_digest(
        x_api_key, API_KEY
    ):
        raise HTTPException(401, "Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Development bootstrap only; use Alembic in production.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="HAT Converse Document Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/v1/documents",
    response_model=DocumentResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]

    if not filename or len(filename) > 255:
        raise HTTPException(400, "Invalid filename")

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    if file.content_type not in (
        "application/pdf",
        "application/octet-stream",
    ):
        raise HTTPException(400, "Invalid content type")

    try:
        contents = await file.read(MAX_FILE_SIZE + 1)
    finally:
        await file.close()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, "PDF exceeds 10 MiB limit")

    if not contents.startswith(b"%PDF-"):
        raise HTTPException(400, "Invalid PDF signature")

    doc = Document(
        filename=filename,
        content_type="application/pdf",
        size_bytes=len(contents),
        sha256=hashlib.sha256(contents).hexdigest(),
        file_data=contents,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Process PDF after the upload response is sent
    background_tasks.add_task(
        process_uploaded_document,
        doc.id,
    )

    return doc




@app.get(
    "/v1/documents",
    dependencies=[Depends(require_api_key)],
)
def list_documents(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, "Invalid pagination")

    total = db.scalar(select(func.count()).select_from(Document))

    rows = db.execute(
        select(
            Document.id,
            Document.filename,
            Document.content_type,
            Document.size_bytes,
            Document.sha256,
            Document.created_at,
        )
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            DocumentResponse(
                id=row.id,
                filename=row.filename,
                content_type=row.content_type,
                size_bytes=row.size_bytes,
                sha256=row.sha256,
                created_at=row.created_at,
            )
            for row in rows
        ],
    }


@app.get(
    "/v1/documents/{document_id}",
    response_model=DocumentResponse,
    dependencies=[Depends(require_api_key)],
)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@app.get(
    "/v1/documents/{document_id}/download",
    dependencies=[Depends(require_api_key)],
)
def download_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")

    return Response(
        content=doc.file_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="document-{doc.id}.pdf"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.delete(
    "/v1/documents/{document_id}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")

    db.delete(doc)
    db.commit()


@app.post(
    "/v1/documents/{document_id}/process",
    dependencies=[Depends(require_api_key)],
)
def process_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    try:
        return index_pdf(
            document_id=document.id,
            filename=document.filename,
            pdf_bytes=document.file_data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc



class AskDocumentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


@app.post(
    "/v1/documents/{document_id}/ask",
    dependencies=[Depends(require_api_key)],
)
def ask_document(
    document_id: UUID,
    request: AskDocumentRequest,
    db: Session = Depends(get_db),
):
    # Verify that the PDF exists in PostgreSQL.
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return answer_document_question(
        document_id=document_id,
        question=request.question,
        limit=request.limit,
    )

