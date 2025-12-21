from __future__ import annotations
from typing import Any
from nord_skc.model import ReadResult

class BaseDriver:
    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def read_once(self) -> ReadResult:
        raise NotImplementedError

    def write_command(self, name: str, value: Any) -> bool:
        # позже добавим команды управления
        return False
