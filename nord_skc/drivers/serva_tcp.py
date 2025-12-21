from __future__ import annotations
import socket
from typing import Dict, List, Optional
from nord_skc.model import ReadResult
from .base import BaseDriver

class ServaTcpDriver(BaseDriver):
    """
    По дампу: TCP, порт 6565, запрос "$HELLO", ответ строка (похожа на CSV).
    """
    def __init__(
        self,
        ip: str,
        port: int = 6565,
        hello: str = "$HELLO\r\n",
        timeout_s: float = 2.0,
        field_names: Optional[List[str]] = None,
    ):
        self.ip = ip
        self.port = port
        self.hello = hello.encode("ascii", errors="ignore")
        self.timeout_s = timeout_s
        self.sock: socket.socket | None = None
        self.field_names = field_names or []

    def connect(self) -> None:
        self.sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_s)
        self.sock.settimeout(self.timeout_s)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _recv_line(self) -> str:
        assert self.sock is not None
        buf = bytearray()
        while True:
            b = self.sock.recv(1)
            if not b:
                break
            buf += b
            if b == b"\n" or len(buf) > 65535:
                break
        return buf.decode("utf-8", errors="ignore").strip()

    def read_once(self) -> ReadResult:
        if not self.sock:
            return ReadResult(ok=False, values={}, error="not connected")

        try:
            self.sock.sendall(self.hello)
            line = self._recv_line()
            if not line:
                return ReadResult(ok=False, values={}, error="empty reply")

            parts = [p.strip() for p in line.split(",") if p.strip() != ""]
            nums: list[float] = []
            for p in parts:
                try:
                    nums.append(float(p))
                except ValueError:
                    # текстовые токены игнорируем (ID/дата/служебное)
                    continue

            if not nums:
                return ReadResult(ok=False, values={}, error=f"no numeric fields in reply: {line[:80]}")

            if self.field_names and len(self.field_names) == len(nums):
                keys = self.field_names
            else:
                keys = [f"field_{i:02d}" for i in range(1, len(nums) + 1)]

            values: Dict[str, float] = {k: v for k, v in zip(keys, nums)}
            return ReadResult(ok=True, values=values)

        except Exception as e:
            return ReadResult(ok=False, values={}, error=str(e))
