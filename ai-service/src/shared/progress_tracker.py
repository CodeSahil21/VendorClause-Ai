import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class ProgressTracker:
    def __init__(self, file_path: str = "progress.json"):
        self.file_path = Path(__file__).parent.parent / file_path

    def update(self, status: str, document_id: str = None, progress: int = 0, stage: str = None) -> None:
        data = {
            "status": status,
            "current_document": document_id,
            "progress": progress,
            "stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.file_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.debug(f"Progress file write skipped: {e}")

    def get(self) -> dict:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"status": "idle"}
