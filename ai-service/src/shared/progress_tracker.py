import json
from datetime import datetime
from pathlib import Path

class ProgressTracker:
    def __init__(self, file_path="progress.json"):
        self.file_path = Path(__file__).parent.parent / file_path
    
    def update(self, status, document_id=None, progress=0, stage=None):
        data = {
            "status": status,
            "current_document": document_id,
            "progress": progress,
            "stage": stage,
            "updated_at": datetime.now().isoformat()
        }
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get(self):
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except:
            return {"status": "idle"}
