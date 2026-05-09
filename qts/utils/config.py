"""YAML config loader with pydantic validation."""
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class DataConfig(BaseModel):
    provider: str = "akshare"
    cache_dir: str = "data/raw"
    clean_dir: str = "data/clean"
    factors_dir: str = "data/factors"


class BacktestConfig(BaseModel):
    initial_cash: float = 1_000_000
    commission_rate: float = 0.00025
    stamp_tax_rate: float = 0.0005
    min_commission: float = 5.0
    slippage_bps: float = 10.0
    lot_size: int = 100


class StrategyConfig(BaseModel):
    name: str
    universe: str = "HS300"
    rebalance: str = "weekly"
    filters: dict[str, Any] = {}
    factors: dict[str, dict[str, float]] = {}
    portfolio: dict[str, Any] = {}
    risk: dict[str, float] = {}
    execution: dict[str, Any] = {}


class RiskConfig(BaseModel):
    max_position_weight: float = 0.08
    max_drawdown_cut: float = 0.10
    max_industry_weight: float = 0.30
    max_daily_turnover: float = 0.50
    blacklist: list[str] = []


class BrokerConfig(BaseModel):
    gateway: str = "mock"
    account_id: str = ""
    host: str = ""
    port: int = 0


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return parsed dict."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(model_cls: type[BaseModel], path: str | Path) -> BaseModel:
    """Load a YAML config file and validate with pydantic model."""
    data = load_yaml(path)
    return model_cls(**data)


def get_project_root() -> Path:
    """Return the project root directory (two levels up from this file)."""
    return Path(__file__).resolve().parent.parent.parent
