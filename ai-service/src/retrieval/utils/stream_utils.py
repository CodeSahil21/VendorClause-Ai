# Standard library
import json
from typing import Any

# Third-party
from redis.asyncio import Redis


async def publish_stream_event(redis_client: Redis, session_id: str, event: str, payload: dict[str, Any]) -> None:
    channel = f"query:stream:{session_id}"
    message = {"event": event, "payload": payload}
    await redis_client.publish(channel, json.dumps(message))


__all__ = ["publish_stream_event"]
