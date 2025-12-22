from __future__ import annotations

import socket
from typing import Dict, List, Optional

from nord_skc.model import ReadResult
from .base import BaseDriver


class ServaTcpDriver(BaseDriver):
    """
    SERVA (Bradley) по дампу:
      - TCP 6565
      - запрос: b"$HELLO" (6 байт, без CRLF)
      - ответ: ASCII строка CSV, заканчивается \r\n
        полей обычно 16: id, model, timestamp, 12 float, status
    """

    def __init__(
        self,
        ip: str,
        port: int = 6565,
        timeout_s: float = 2.0,
        field_names: Optional[List[str]] = None,
    ):
        self.ip = ip
        self.port = port
        self.timeout_s = timeout_s
        self.sock: socket.socket | None = None
        self._rx = bytearray()

        # названия 12 каналов
        self.field_names = field_names or [f"field_{i:02d}" for i in range(1, 13)]

    def connect(self) -> None:
        self.sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_s)
        self.sock.settimeout(self.timeout_s)
        self._rx.clear()

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _recv_line_crlf(self) -> str:
        """Читает одну строку, разделитель \r\n. Возвращает строку без CRLF."""
        assert self.sock is not None

        while True:
            idx = self._rx.find(b"\r\n")
            if idx >= 0:
                line = bytes(self._rx[:idx])
                del self._rx[:idx + 2]
                return line.decode("ascii", errors="ignore")

            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("remote closed connection")
            self._rx.extend(chunk)

            if len(self._rx) > 1024 * 1024:
                raise ValueError("rx buffer overflow")

    def read_once(self) -> ReadResult:
        if not self.sock:
            return ReadResult(ok=False, values={}, error="not connected")

        try:
            # ВАЖНО: без \r\n (как в дампе)
            self.sock.sendall(b"$HELLO")

            line = self._recv_line_crlf().strip()
            if not line:
                return ReadResult(ok=False, values={}, error="empty reply")

            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 16:
                return ReadResult(ok=False, values={}, error=f"bad reply (fields={len(parts)}): {line[:120]}")

            # ожидаем: 0=id, 1=model, 2=ts, 3..14=12 float, 15=status
            try:
                nums = [float(x) for x in parts[3:15]]
            except ValueError as e:
                return ReadResult(ok=False, values={}, error=f"cannot parse floats: {e}; line={line[:120]}")

            if len(nums) != 12:
                return ReadResult(ok=False, values={}, error=f"unexpected float count: {len(nums)}; line={line[:120]}")

            values: Dict[str, float] = dict(zip(self.field_names, nums))
            return ReadResult(ok=True, values=values)

        except Exception as e:
            return ReadResult(ok=False, values={}, error=str(e))
