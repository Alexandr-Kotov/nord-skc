from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import yaml

@dataclass
class AppConfig:
    name: str
    poll_hz: int
    history_seconds: int

@dataclass
class AssetConfig:
    id: str
    fleet_no: int
    plate: str
    type: str
    ip: str
    extra: Dict[str, Any]

@dataclass
class Config:
    app: AppConfig
    assets: List[AssetConfig]

def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    app_raw = raw.get("app", {})
    app = AppConfig(
        name=str(app_raw.get("name", "NORD SKC")),
        poll_hz=int(app_raw.get("poll_hz", 1)),
        history_seconds=int(app_raw.get("history_seconds", 900)),
    )

    assets: List[AssetConfig] = []
    for a in (raw.get("assets") or []):
        a = dict(a)
        asset = AssetConfig(
            id=str(a.pop("id")),
            fleet_no=int(a.pop("fleet_no", 0)),
            plate=str(a.pop("plate", "")),
            type=str(a.pop("type")),
            ip=str(a.pop("ip")),
            extra=a,   # всё остальное (порт, rack/slot, tags...)
        )
        assets.append(asset)

    return Config(app=app, assets=assets)
