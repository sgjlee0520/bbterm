from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    databento_api_key: str | None
    db_path: Path
    cost_cap_usd: float
    databento_dataset: str
    lambda_api_key: str | None = None


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(root: Path | None = None) -> Config:
    root = root or Path.cwd()
    env = {**_load_dotenv(root / ".env"), **os.environ}
    return Config(
        databento_api_key=env.get("DATABENTO_API_KEY"),
        db_path=Path(env.get("BBTERM_DB_PATH", str(root / "data" / "market.duckdb"))),
        cost_cap_usd=float(env.get("BBTERM_COST_CAP_USD", "1.0")),
        databento_dataset=env.get("BBTERM_DATASET", "EQUS.MINI"),
        lambda_api_key=env.get("LAMBDA_API_KEY"),
    )
