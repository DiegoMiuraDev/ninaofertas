"""Fonte: Mercado Livre — API oficial de busca.

Importante: em 2026 o endpoint `/sites/MLB/search` passou a exigir um
access_token válido para a maioria das aplicações (chamadas anônimas retornam
403). Configure `MERCADOLIVRE_APP_ID`/`MERCADOLIVRE_APP_SECRET` no `.env` com
as credenciais de uma aplicação criada em
https://developers.mercadolivre.com.br/ — o scraper faz o client_credentials
grant automaticamente e reusa o token até expirar. Sem credenciais, a fonte é
pulada silenciosamente (log de aviso uma vez) sem derrubar o bot.
"""
from __future__ import annotations

import time

import httpx

from config import load_filtros, settings
from logger import logger
from scraper.base import OfertaCapturada, Scraper

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
API_URL = "https://api.mercadolibre.com/sites/MLB/search"

_token_cache: dict = {"access_token": None, "expira_em": 0}


def _obter_token(client: httpx.Client) -> str | None:
    if not settings.mercadolivre_app_id or not settings.mercadolivre_app_secret:
        return None

    if _token_cache["access_token"] and time.time() < _token_cache["expira_em"]:
        return _token_cache["access_token"]

    resp = client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.mercadolivre_app_id,
            "client_secret": settings.mercadolivre_app_secret,
        },
    )
    resp.raise_for_status()
    dados = resp.json()
    _token_cache["access_token"] = dados["access_token"]
    _token_cache["expira_em"] = time.time() + dados.get("expires_in", 21600) - 60
    return _token_cache["access_token"]


class MercadoLivreScraper(Scraper):
    nome_fonte = "Mercado Livre"
    _avisou_sem_credenciais = False

    def _termos_busca(self) -> list[str]:
        """Prioridade: termos_busca (nicho) > palavras_chave > categorias."""
        filtros = load_filtros()
        return (
            filtros.get("termos_busca")
            or filtros.get("palavras_chave")
            or filtros.get("categorias")
            or ["oferta"]
        )

    def buscar(self) -> list[OfertaCapturada]:
        ofertas: list[OfertaCapturada] = []
        with httpx.Client(timeout=self.timeout) as client:
            token = _obter_token(client)
            if token is None:
                if not MercadoLivreScraper._avisou_sem_credenciais:
                    logger.warning(
                        "[Mercado Livre] MERCADOLIVRE_APP_ID/SECRET não configurados — "
                        "fonte pulada. Crie um app em https://developers.mercadolivre.com.br/"
                    )
                    MercadoLivreScraper._avisou_sem_credenciais = True
                return []

            headers = {"Authorization": f"Bearer {token}"}
            for termo in self._termos_busca():
                resp = client.get(API_URL, params={"q": termo, "limit": 30}, headers=headers)
                resp.raise_for_status()
                dados = resp.json()
                for item in dados.get("results", []):
                    preco = item.get("price")
                    preco_anterior = item.get("original_price")
                    if preco is None:
                        continue
                    # category_id (ex: MLB1055) não serve no filtro por nome —
                    # nicho vem de palavras_chave / produtos_especificos.
                    ofertas.append(
                        OfertaCapturada(
                            nome=item.get("title", ""),
                            preco=float(preco),
                            preco_anterior=float(preco_anterior) if preco_anterior else None,
                            loja="Mercado Livre",
                            url=item.get("permalink", ""),
                            categoria=None,
                            imagem=item.get("thumbnail"),
                            sku=item.get("id"),
                        )
                    )
        return ofertas
