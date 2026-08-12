"""Loop principal: busca ofertas em todas as fontes, filtra, deduplica, formata
e envia para o WhatsApp. Isola erros por oferta/fonte — nada aqui derruba o bot."""
from __future__ import annotations

import dedup
import database
import formatter
import whatsapp
from config import load_filtros, settings
from filters import passa_nos_filtros
from logger import logger
from scraper import FONTES
from scraper.base import OfertaCapturada


def _processar_oferta(session, oferta: OfertaCapturada, filtros: dict) -> None:
    passou, motivo = passa_nos_filtros(oferta, filtros)
    if not passou:
        logger.debug(f"Descartada '{oferta.nome[:60]}': {motivo}")
        return

    logger.info(f"Oferta válida encontrada: {oferta.nome}")
    if oferta.desconto is not None:
        logger.info(f"Desconto: {oferta.desconto}%")

    oferta_db = database.upsert_oferta(
        session,
        {
            "nome": oferta.nome,
            "preco": oferta.preco,
            "preco_anterior": oferta.preco_anterior,
            "desconto": oferta.desconto,
            "loja": oferta.loja,
            "categoria": oferta.categoria,
            "url": oferta.url,
            "imagem": oferta.imagem,
            "sku": oferta.sku,
        },
    )

    pode_enviar, motivo_dedup = dedup.deve_enviar(session, oferta_db.id, oferta.preco, settings.reenvio_queda_minima)
    if not pode_enviar:
        logger.info(f"Oferta já enviada. Pulando. ({motivo_dedup})")
        return

    max_hora = filtros.get("max_ofertas_por_hora")
    max_dia = filtros.get("max_ofertas_por_dia")
    if max_hora and database.contar_envios_ultima_hora(session) >= max_hora:
        logger.warning(f"Limite de {max_hora} ofertas/hora atingido. Pulando envio.")
        return
    if max_dia and database.contar_envios_hoje(session) >= max_dia:
        logger.warning(f"Limite de {max_dia} ofertas/dia atingido. Pulando envio.")
        return

    logger.info(f"Oferta ainda não enviada. ({motivo_dedup})")
    mensagem = formatter.montar_mensagem(oferta)

    logger.info("Enviando para WhatsApp...")
    sucesso = whatsapp.enviar_mensagem(mensagem, imagem=oferta.imagem)

    database.registrar_envio(
        session,
        oferta_id=oferta_db.id,
        grupo=settings.whatsapp_group_id,
        mensagem=mensagem,
        preco=oferta.preco,
        status="sucesso" if sucesso else "falha",
    )

    if sucesso:
        logger.info("✓ Oferta enviada com sucesso.")
    else:
        logger.error("✗ Falha ao enviar oferta para o WhatsApp.")


def ciclo() -> None:
    """Executa uma rodada completa de monitoramento em todas as fontes cadastradas."""
    logger.info("Buscando novas ofertas...")
    filtros = load_filtros()

    todas_ofertas: list[OfertaCapturada] = []
    for fonte in FONTES:
        todas_ofertas.extend(fonte.executar())

    logger.info(f"{len(todas_ofertas)} ofertas encontradas.")

    with database.get_session() as session:
        for oferta in todas_ofertas:
            try:
                _processar_oferta(session, oferta, filtros)
            except Exception as e:
                logger.error(f"Erro ao processar oferta '{oferta.nome[:60]}': {e}")

    logger.info(f"Próxima verificação em {settings.check_interval}s.")
