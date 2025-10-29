import hashlib
import time
from typing import Literal

import boto3
from botocore.client import Config as BotoConfig
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.session import get_db


router = APIRouter(prefix="/media", tags=["media"])


class PresignRequest(BaseModel):
    content_type: str
    ext: Literal["jpg", "jpeg", "png", "webp"]


class PresignResponse(BaseModel):
    url: str
    fields: dict = Field(default_factory=dict)
    key: str


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


@router.post("/presign", response_model=PresignResponse)
def presign_upload(req: PresignRequest, db=Depends(get_db)):
    now = int(time.time())
    digest = hashlib.sha256(f"{now}:{req.content_type}".encode()).hexdigest()[:16]
    key = f"uploads/{now}/{digest}.{req.ext}"
    client = _s3_client()
    try:
        presigned = client.generate_presigned_post(
            Bucket=settings.s3_bucket,
            Key=key,
            Fields={"Content-Type": req.content_type},
            Conditions=[["eq", "$Content-Type", req.content_type]],
            ExpiresIn=300,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"presign failed: {e}")
    return PresignResponse(url=presigned["url"], fields=presigned["fields"], key=key)


class SubmitRequest(BaseModel):
    key: str
    trip_id: int | None = None
    label_hint: str | None = None


@router.post("/submit")
def submit_image(_: SubmitRequest, db=Depends(get_db)):
    # Stub: enqueue later via SQS in pipeline service
    return {"status": "queued"}


