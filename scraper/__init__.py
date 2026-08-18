"""Registro de fontes de ofertas. Para adicionar uma nova fonte, crie um
arquivo com uma subclasse de `Scraper` e adicione uma instância à lista abaixo.

Foco atual: Mercado Livre + Amazon + Shopee (API afiliados).
Pelando/Magalu ficam fora do pipeline ativo.
"""
from scraper.amazon import AmazonScraper
from scraper.base import OfertaCapturada, Scraper
from scraper.mercadolivre import MercadoLivreScraper
from scraper.shopee import ShopeeScraper

FONTES: list[Scraper] = [
    MercadoLivreScraper(),
    AmazonScraper(),
    ShopeeScraper(),
]

__all__ = ["FONTES", "Scraper", "OfertaCapturada"]
