"""Controle de duplicidade: a oferta é identificada pela URL (chave única em
`ofertas`). Só reenviamos uma oferta já enviada se o preço caiu o suficiente
desde o último envio."""
from __future__ import annotations

from sqlalchemy.orm import Session

import database


def deve_enviar(session: Session, oferta_id: int, preco_atual: float, queda_minima_pct: float) -> tuple[bool, str]:
    envio_anterior = database.ultimo_envio(session, oferta_id)

    if envio_anterior is None:
        return True, "oferta ainda não enviada"

    preco_anterior_envio = envio_anterior.preco_enviado
    if not preco_anterior_envio or preco_anterior_envio <= 0:
        return False, "já enviada anteriormente"

    if preco_atual >= preco_anterior_envio:
        return False, "já enviada anteriormente e preço não caiu"

    queda_pct = (1 - preco_atual / preco_anterior_envio) * 100
    if queda_pct >= queda_minima_pct:
        return True, f"preço caiu {queda_pct:.1f}% desde o último envio (R${preco_anterior_envio:.2f} -> R${preco_atual:.2f})"

    return False, f"já enviada e queda de {queda_pct:.1f}% é menor que o mínimo de {queda_minima_pct}%"
