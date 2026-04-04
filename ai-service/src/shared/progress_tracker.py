# Standard library
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class ProgressTracker:
    def __init__(self, file_path: str | None = None):
        resolved_name = file_path or f"progress-{os.getpid()}.json"
        self.file_path = Path(__file__).parent.parent / resolved_name

    def update(self, status: str, document_id: str = None, progress: int = 0, stage: str = None) -> None:
        data = {
            "status": status,
            "current_document": document_id,
            "progress": progress,
            "stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            tmp_path = self.file_path.with_name(f".{self.file_path.name}.{os.getpid()}.tmp")
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.file_path)
        except OSError as e:
            logger.debug(f"Progress file write skipped: {e}")

    def get(self) -> dict:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"status": "idle"}
