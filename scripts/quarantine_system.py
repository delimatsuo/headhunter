import os
import uuid
from datetime import datetime
from typing import Dict, Any


class QuarantineSystem:
    def __init__(self, quarantine_dir: str = ".quarantine"):
        self.quarantine_dir = quarantine_dir
        os.makedirs(self.quarantine_dir, exist_ok=True)

    def store(self, raw_payload: str, metadata: Dict[str, Any]) -> str:
        qid = str(uuid.uuid4())
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        base = os.path.join(self.quarantine_dir, f"{ts}_{qid}")
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(raw_payload)
        with open(base + ".meta", "w", encoding="utf-8") as f:
            for k, v in metadata.items():
                f.write(f"{k}: {v}\n")
        return qid

