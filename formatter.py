"""Monta a mensagem do WhatsApp a partir do template configurável em config.json."""
from __future__ import annotations

from datetime import datetime

from config import load_filtros
from scraper.base import OfertaCapturada

TEMPLATE_PADRAO = (
    "🔥 OFERTA ENCONTRADA!\n\n"
    "🛒 {nome}\n\n"
    "💰 De: R$ {preco_anterior}\n"
    "🔥 Por: R$ {preco}\n"
    "📉 {desconto}% OFF\n\n"
    "🏪 {loja}\n\n"
    "👉 COMPRAR:\n{url}\n\n"
    "⏰ Oferta encontrada às {hora}"
)


def _preco_fmt(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def montar_mensagem(oferta: OfertaCapturada) -> str:
    filtros = load_filtros()
    eh_campanha = (oferta.categoria or "").lower() in {"campanha", "cupom", "promocao", "promoção"}

    if eh_campanha:
        template = filtros.get(
            "mensagem_campanha_template",
            "🎫 CAMPANHA / CUPOM SHOPEE!\n\n📌 {nome}\n\n🏪 {loja}\n\n👉 ACESSAR:\n{url}\n\n⏰ {hora}",
        )
    else:
        template = filtros.get("mensagem_template", TEMPLATE_PADRAO)

    preco_anterior = oferta.preco_anterior if oferta.preco_anterior else oferta.preco
    desconto = oferta.desconto if oferta.desconto is not None else 0

    return template.format(
        nome=oferta.nome,
        preco=_preco_fmt(oferta.preco),
        preco_anterior=_preco_fmt(preco_anterior),
        desconto=round(desconto, 1),
        loja=oferta.loja,
        url=oferta.url,
        hora=oferta.capturado_em.strftime("%H:%M"),
    )
