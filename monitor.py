"""Loop principal: busca ofertas, filtra, deduplica e envia ao WhatsApp.

1ª fase (baseline): marca estoque atual sem enviar.
Depois: só ofertas novas/quentes — com freio anti-ban no WhatsApp.
"""
from __future__ import annotations

import affiliate
import dedup
import database
import formatter
import whatsapp
from config import load_filtros, settings
from filters import passa_nos_filtros
from logger import logger
from scraper import FONTES
from scraper.base import OfertaCapturada

_baseline_ciclos_feitos = 0
_ciclo_n = 0


def _intercalar_lojas(ofertas: list[OfertaCapturada], prioridade: str) -> list[OfertaCapturada]:
    """MELI e Shopee se revezam; `prioridade` começa a fila pra não ficar só uma loja."""
    from collections import defaultdict, deque

    filas: dict[str, deque] = defaultdict(deque)
    for o in ofertas:
        filas[o.loja].append(o)
    lojas = sorted(filas.keys(), key=lambda l: (0 if l == prioridade else 1, l))
    out: list[OfertaCapturada] = []
    while any(filas.values()):
        for loja in lojas:
            if filas[loja]:
                out.append(filas[loja].popleft())
    return out


def _salvar_oferta(session, oferta: OfertaCapturada):
    return database.upsert_oferta(
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


def _baseline_oferta(session, oferta: OfertaCapturada, filtros: dict) -> bool:
    passou, motivo = passa_nos_filtros(oferta, filtros)
    if not passou:
        logger.debug(f"Baseline descartada '{oferta.nome[:60]}': {motivo}")
        return False

    oferta_db = _salvar_oferta(session, oferta)
    if database.ja_conhecida(session, oferta_db.id):
        return False
    database.registrar_visto(session, oferta_db.id, oferta.preco)
    return True


def _freio_anti_ban(session, filtros: dict) -> tuple[bool, str]:
    """Ritmo estilo grupo de ofertas: rajada curta + pausa, sem spam infinito.

    Ex.: 3–4 msgs em poucos minutos, depois ~25 min de silêncio.
    """
    from datetime import datetime, timedelta

    decorridos = database.minutos_desde_ultimo_envio(session)

    # Espaço mínimo entre qualquer envio (ex.: 2 min).
    intervalo_min = filtros.get("intervalo_minutos_entre_ofertas")
    if intervalo_min and decorridos is not None and decorridos < float(intervalo_min):
        falta = float(intervalo_min) - decorridos
        return False, f"freio: intervalo {intervalo_min} min na rajada (faltam ~{falta:.0f} min)"

    # Se já mandou N na janela curta, obriga pausa longa antes da próxima rajada.
    max_rajada = int(filtros.get("max_ofertas_por_rajada") or 0)
    janela = float(filtros.get("janela_rajada_minutos") or 12)
    pausa = float(filtros.get("pausa_entre_rajadas_minutos") or 0)
    if max_rajada and pausa:
        n_janela = database.contar_envios_desde(
            session, datetime.now() - timedelta(minutes=janela)
        )
        if n_janela >= max_rajada and decorridos is not None and decorridos < pausa:
            falta = pausa - decorridos
            return False, (
                f"freio: rajada de {n_janela}/{max_rajada} na janela — "
                f"pausa {pausa:.0f} min (faltam ~{falta:.0f} min)"
            )

    max_hora = filtros.get("max_ofertas_por_hora")
    if max_hora and database.contar_envios_ultima_hora(session) >= int(max_hora):
        return False, f"freio: limite {max_hora}/hora atingido"

    max_dia = filtros.get("max_ofertas_por_dia")
    if max_dia and database.contar_envios_hoje(session) >= int(max_dia):
        return False, f"freio: limite {max_dia}/dia atingido"

    return True, ""


def _processar_oferta(session, oferta: OfertaCapturada, filtros: dict) -> str:
    """Retorna: 'enviou' | 'pulou' | 'freio' (parar o ciclo de envios)."""
    passou, motivo = passa_nos_filtros(oferta, filtros)
    if not passou:
        logger.debug(f"Descartada '{oferta.nome[:60]}': {motivo}")
        return "pulou"

    oferta_db = _salvar_oferta(session, oferta)

    pode_enviar, motivo_dedup = dedup.deve_enviar(
        session,
        oferta_db.id,
        oferta.preco,
        settings.reenvio_queda_minima,
        nome=oferta.nome,
        sku=oferta.sku,
        loja=oferta.loja,
    )
    if not pode_enviar:
        # Marca como vista pra não insistir em duplicata nos próximos ciclos.
        if "duplicata" in motivo_dedup or "igual/parecida" in motivo_dedup:
            if not database.ja_conhecida(session, oferta_db.id):
                database.registrar_visto(session, oferta_db.id, oferta.preco)
        logger.debug(f"Pulando '{oferta.nome[:60]}': {motivo_dedup}")
        return "pulou"

    ok_ritmo, motivo_freio = _freio_anti_ban(session, filtros)
    if not ok_ritmo:
        logger.warning(motivo_freio)
        return "freio"

    logger.info(f"Oferta NOVA: {oferta.nome}")
    if oferta.desconto is not None:
        logger.info(f"Desconto: {oferta.desconto}%")
    logger.info(f"Motivo: {motivo_dedup}")

    oferta.url = affiliate.garantir_afiliado(oferta.loja, oferta.url)
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
        logger.info("Oferta enviada com sucesso.")
    else:
        logger.error("Falha ao enviar oferta para o WhatsApp.")
    return "enviou"


def ciclo() -> None:
    global _baseline_ciclos_feitos, _ciclo_n

    logger.info("Buscando novas ofertas...")
    filtros = load_filtros()
    baseline_alvo = int(filtros.get("baseline_ciclos") or 5)
    max_por_ciclo = int(filtros.get("max_ofertas_por_ciclo") or 1)

    todas_ofertas: list[OfertaCapturada] = []
    for fonte in FONTES:
        todas_ofertas.extend(fonte.executar())

    _ciclo_n += 1
    prioridade = "Shopee" if _ciclo_n % 2 == 1 else "Mercado Livre"
    todas_ofertas = _intercalar_lojas(todas_ofertas, prioridade)

    logger.info(f"{len(todas_ofertas)} ofertas encontradas na varredura.")

    with database.get_session() as session:
        if _baseline_ciclos_feitos < baseline_alvo:
            _baseline_ciclos_feitos += 1
            logger.info(
                f"Baseline {_baseline_ciclos_feitos}/{baseline_alvo}: "
                "marcando estoque atual (sem enviar)."
            )
            novas_marcadas = 0
            for oferta in todas_ofertas:
                try:
                    if _baseline_oferta(session, oferta, filtros):
                        novas_marcadas += 1
                except Exception as e:
                    logger.error(f"Erro no baseline '{oferta.nome[:60]}': {e}")
            logger.info(f"Baseline: +{novas_marcadas} ofertas marcadas neste ciclo.")
            if _baseline_ciclos_feitos >= baseline_alvo:
                logger.info(
                    "Baseline concluída. Próximas novidades serão blipadas "
                    "com freio anti-ban (intervalo/limites do config.json)."
                )
        else:
            enviadas_ciclo = 0
            for oferta in todas_ofertas:
                try:
                    resultado = _processar_oferta(session, oferta, filtros)
                except Exception as e:
                    logger.error(f"Erro ao processar oferta '{oferta.nome[:60]}': {e}")
                    continue
                if resultado == "freio":
                    break
                if resultado == "enviou":
                    enviadas_ciclo += 1
                    if enviadas_ciclo >= max_por_ciclo:
                        logger.info(
                            f"Freio anti-ban: já enviou {enviadas_ciclo} neste ciclo "
                            f"(máx {max_por_ciclo})."
                        )
                        break

    logger.info(f"Próxima verificação em {settings.check_interval}s.")
