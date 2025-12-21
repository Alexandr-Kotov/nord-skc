from __future__ import annotations
from typing import Dict
import struct

import snap7
from nord_skc.model import ReadResult
from .base import BaseDriver

def _parse_value(raw: bytes, dtype: str) -> float:
    dt = dtype.lower()
    # Siemens S7: REAL/INT big-endian
    if dt == "real":
        return float(struct.unpack(">f", raw)[0])
    if dt == "int":
        return float(struct.unpack(">h", raw)[0])
    if dt == "dint":
        return float(struct.unpack(">i", raw)[0])
    raise ValueError(f"Unsupported dtype: {dtype}")

class SiemensS7Driver(BaseDriver):
    def __init__(self, ip: str, rack: int, slot: int, tags: dict):
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self.tags = tags  # {name: {db,start,size,dtype}}
        self.client = snap7.client.Client()

    def connect(self) -> None:
        self.client.connect(self.ip, self.rack, self.slot)

    def close(self) -> None:
        try:
            self.client.disconnect()
        except Exception:
            pass

    def read_once(self) -> ReadResult:
        try:
            values: Dict[str, float] = {}
            for name, t in (self.tags or {}).items():
                db = int(t["db"])
                start = int(t["start"])
                size = int(t["size"])
                dtype = str(t["dtype"])
                raw = self.client.db_read(db, start, size)
                values[name] = _parse_value(raw, dtype)
            return ReadResult(ok=True, values=values)
        except Exception as e:
            return ReadResult(ok=False, values={}, error=str(e))
