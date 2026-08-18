"""Fonte: Shopee BR — API oficial de Afiliados (GraphQL + HMAC-SHA256).

Requer `SHOPEE_APP_ID` e `SHOPEE_APP_SECRET` no `.env` (Open API do painel
de afiliados). Sem credenciais, a fonte é pulada com aviso.

Docs / playground não oficiais de referência:
https://www.affiliateshopee.com.br/documentacao

O campo `offerLink` já vem com tracking de afiliado — usamos ele na mensagem.
"""
from __future__ import annotations

import hashlib
import json
import time

import httpx

from config import load_filtros, settings
from logger import logger
from scraper.base import OfertaCapturada, Scraper

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"


def _assinar(app_id: str, secret: str, timestamp: int, payload: str) -> str:
    raw = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _preco_float(valor) -> float | None:
    if valor is None:
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _desconto_pct(valor) -> float | None:
    """priceDiscountRate pode vir como 15, '15' ou '0.15'."""
    d = _preco_float(valor)
    if d is None:
        return None
    if 0 < d <= 1:
        return round(d * 100, 1)
    return round(d, 1)


class ShopeeScraper(Scraper):
    nome_fonte = "Shopee"
    _avisou_sem_credenciais = False

    def _termos_busca(self) -> list[str]:
        filtros = load_filtros()
        return (
            filtros.get("termos_busca")
            or filtros.get("palavras_chave")
            or filtros.get("categorias")
            or ["oferta"]
        )

    def _graphql(self, client: httpx.Client, query: str) -> dict:
        app_id = settings.shopee_app_id
        secret = settings.shopee_app_secret
        payload_obj = {"query": query}
        payload = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False)
        timestamp = int(time.time())
        signature = _assinar(app_id, secret, timestamp, payload)
        headers = {
            "Content-Type": "application/json",
            "Authorization": (
                f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}"
            ),
        }
        resp = client.post(API_URL, content=payload.encode("utf-8"), headers=headers)
        resp.raise_for_status()
        dados = resp.json()
        if dados.get("errors"):
            msgs = "; ".join(
                e.get("message") or e.get("extensions", {}).get("message") or str(e)
                for e in dados["errors"]
            )
            raise RuntimeError(f"GraphQL Shopee: {msgs}")
        return dados.get("data") or {}

    def buscar(self) -> list[OfertaCapturada]:
        if not settings.shopee_app_id or not settings.shopee_app_secret:
            if not ShopeeScraper._avisou_sem_credenciais:
                logger.warning(
                    "[Shopee] SHOPEE_APP_ID/SECRET não configurados — fonte pulada. "
                    "Peça acesso Open API no painel de afiliados Shopee."
                )
                ShopeeScraper._avisou_sem_credenciais = True
            return []

        ofertas: list[OfertaCapturada] = []
        with httpx.Client(timeout=self.timeout) as client:
            for termo in self._termos_busca():
                # Escapa aspas na keyword pra não quebrar a query GraphQL.
                keyword = termo.replace('"', '\\"')
                query = f"""
                {{
                  productOfferV2(
                    keyword: "{keyword}",
                    listType: 0,
                    sortType: 2,
                    page: 1,
                    limit: 20
                  ) {{
                    nodes {{
                      itemId
                      productName
                      productLink
                      offerLink
                      imageUrl
                      priceMin
                      priceMax
                      priceDiscountRate
                      shopName
                    }}
                  }}
                }}
                """
                try:
                    data = self._graphql(client, query)
                except Exception as e:
                    logger.warning(f"[Shopee] falha na busca '{termo}': {e}")
                    continue

                nodes = (data.get("productOfferV2") or {}).get("nodes") or []
                for item in nodes:
                    oferta = self._parse_item(item)
                    if oferta:
                        ofertas.append(oferta)
        return ofertas

    def _parse_item(self, item: dict) -> OfertaCapturada | None:
        preco = _preco_float(item.get("priceMin") if item.get("priceMin") is not None else item.get("priceMax"))
        if preco is None:
            return None

        url = item.get("offerLink") or item.get("productLink")
        if not url:
            return None

        desconto = _desconto_pct(item.get("priceDiscountRate"))
        preco_anterior = None
        if desconto and desconto > 0 and desconto < 100:
            preco_anterior = round(preco / (1 - desconto / 100), 2)

        return OfertaCapturada(
            nome=item.get("productName") or "",
            preco=preco,
            preco_anterior=preco_anterior,
            desconto=desconto,
            loja="Shopee",
            url=url,
            imagem=item.get("imageUrl"),
            sku=str(item["itemId"]) if item.get("itemId") is not None else None,
        )
