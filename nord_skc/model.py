from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class ReadResult:
    ok: bool
    values: Dict[str, float]
    error: Optional[str] = None
