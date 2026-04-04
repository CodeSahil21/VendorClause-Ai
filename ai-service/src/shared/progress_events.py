# Standard library
import json
from typing import Literal

# Third-party
from redis.asyncio import Redis


def build_job_progress_event(
    job_id: str,
    document_id: str,
    status: Literal["IN_PROGRESS", "COMPLETED"],
    progress: int,
    stage: str,
) -> dict:
    return {
        "event": "job:progress",
        "jobId": job_id,
        "documentId": document_id,
        "status": status,
        "progress": progress,
        "stage": stage,
    }


async def publish_job_progress(
    redis_client: Redis | None,
    job_id: str | None,
    document_id: str,
    status: Literal["IN_PROGRESS", "COMPLETED"],
    progress: int,
    stage: str,
) -> None:
    if redis_client is None or not job_id:
        return

    if status not in ("IN_PROGRESS", "COMPLETED"):
        raise ValueError(f"Unsupported progress status: {status}")

    payload = build_job_progress_event(
        job_id=job_id,
        document_id=document_id,
        status=status,
        progress=progress,
        stage=stage,
    )
    await redis_client.publish(f"job:{job_id}", json.dumps(payload))
