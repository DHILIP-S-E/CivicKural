"""Voice-note transcription via Amazon Transcribe (spec §2).

Uses a start_transcription_job against an S3 object and polls. A test hook lets the
pipeline run without AWS.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

import boto3
import httpx

from .config import get_settings

_hook: Callable[[bytes], str] | None = None


def set_transcribe_hook(fn: Callable[[bytes], str] | None) -> None:
    global _hook
    _hook = fn


def transcribe_audio(audio: bytes, media_format: str = "ogg") -> str:
    if _hook is not None:
        return _hook(audio)

    s = get_settings()
    s3 = boto3.client("s3", region_name=s.aws_region)
    tx = boto3.client("transcribe", region_name=s.aws_region)

    job = f"ww-{uuid.uuid4().hex}"
    key = f"_transcribe/{job}.{media_format}"
    s3.put_object(Bucket=s.wardwatch_bucket, Key=key, Body=audio)

    tx.start_transcription_job(
        TranscriptionJobName=job,
        Media={"MediaFileUri": f"s3://{s.wardwatch_bucket}/{key}"},
        MediaFormat=media_format,
        IdentifyLanguage=True,
    )
    deadline = time.monotonic() + 120
    try:
        while time.monotonic() < deadline:
            status = tx.get_transcription_job(TranscriptionJobName=job)["TranscriptionJob"]
            state = status["TranscriptionJobStatus"]
            if state == "COMPLETED":
                uri = status["Transcript"]["TranscriptFileUri"]
                return httpx.get(uri, timeout=30).json()["results"]["transcripts"][0]["transcript"]
            if state == "FAILED":
                raise RuntimeError(status.get("FailureReason", "transcription failed"))
            time.sleep(2)
        raise TimeoutError("transcription did not complete within 120 seconds")
    finally:
        s3.delete_object(Bucket=s.wardwatch_bucket, Key=key)
        try:
            tx.delete_transcription_job(TranscriptionJobName=job)
        except tx.exceptions.BadRequestException:
            # AWS does not allow deletion while a job is still running.
            pass
