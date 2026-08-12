"""Entrypoint: inicializa o banco e o agendador do monitoramento periódico."""
from __future__ import annotations

import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

import database
import monitor
from config import settings
from logger import logger


def main() -> None:
    database.init_db()
    logger.info("Bot de Ofertas iniciado.")
    logger.info(f"Verificando novas ofertas a cada {settings.check_interval}s.")

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        monitor.ciclo,
        "interval",
        seconds=settings.check_interval,
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Encerrando bot...")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
