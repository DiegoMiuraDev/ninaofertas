"""Carrega variáveis de ambiente (.env) e critérios de filtro (config.json)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    check_interval: int = field(default_factory=lambda: _env_int("CHECK_INTERVAL", 60))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///ofertas.db"))

    evolution_api_url: str = field(default_factory=lambda: os.getenv("EVOLUTION_API_URL", "http://localhost:8080"))
    evolution_api_key: str = field(default_factory=lambda: os.getenv("EVOLUTION_API_KEY", ""))
    evolution_instance: str = field(default_factory=lambda: os.getenv("EVOLUTION_INSTANCE", ""))
    whatsapp_group_id: str = field(default_factory=lambda: os.getenv("WHATSAPP_GROUP_ID", ""))

    reenvio_queda_minima: float = field(default_factory=lambda: float(os.getenv("REENVIO_QUEDA_MINIMA", 15)))

    mercadolivre_app_id: str = field(default_factory=lambda: os.getenv("MERCADOLIVRE_APP_ID", ""))
    mercadolivre_app_secret: str = field(default_factory=lambda: os.getenv("MERCADOLIVRE_APP_SECRET", ""))
    lomadee_source_id: str = field(default_factory=lambda: os.getenv("LOMADEE_SOURCE_ID", ""))

    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


def load_filtros() -> dict:
    """Lê config.json com os critérios de filtro. Recarregado a cada chamada
    para permitir editar o arquivo sem reiniciar o bot."""
    path = BASE_DIR / "config.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


settings = Settings()
