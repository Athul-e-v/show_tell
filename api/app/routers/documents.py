
import os
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Response

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)

DOCUMENT_SERVICE_URL = os.environ["DOCUMENT_SERVICE_URL"]
DOCUMENT_API_KEY = os.environ["DOCUMENT_API_KEY"]


async def request_document_service(method, path, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = DOCUMENT_API_KEY

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                f"{DOCUMENT_SERVICE_URL}{path}",
                headers=headers,
                **kwargs,
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Document service unavailable",
        )

    return response


def forward_response(response: httpx.Response) -> Response:
    headers = {}
    for name in ("content-disposition", "x-content-type-options"):
        if name in response.headers:
            headers[name] = response.headers[name]

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type", "application/json"
        ),
        headers=headers,
    )


@router.post("")
async def upload_document(file: UploadFile = File(...)):
    contents = await file.read()

    response = await request_document_service(
        "POST",
        "/v1/documents",
        files={
            "file": (
                file.filename,
                contents,
                file.content_type,
            )
        },
    )
    return forward_response(response)


@router.get("")
async def list_documents(limit: int = 20, offset: int = 0):
    response = await request_document_service(
        "GET",
        "/v1/documents",
        params={"limit": limit, "offset": offset},
    )
    return forward_response(response)


@router.get("/{document_id}")
async def get_document(document_id: UUID):
    response = await request_document_service(
        "GET",
        f"/v1/documents/{document_id}",
    )
    return forward_response(response)


@router.get("/{document_id}/download")
async def download_document(document_id: UUID):
    response = await request_document_service(
        "GET",
        f"/v1/documents/{document_id}/download",
    )
    return forward_response(response)


@router.delete("/{document_id}")
async def delete_document(document_id: UUID):
    response = await request_document_service(
        "DELETE",
        f"/v1/documents/{document_id}",
    )
    return forward_response(response)


