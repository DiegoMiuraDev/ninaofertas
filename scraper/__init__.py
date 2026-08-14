"""Registro de fontes de ofertas. Para adicionar uma nova fonte, crie um
arquivo com uma subclasse de `Scraper` e adicione uma instância à lista abaixo.

Foco atual: Mercado Livre (API oficial) + Amazon BR (scraping).
Pelando/Magalu ficam fora do pipeline ativo.
"""
from scraper.amazon import AmazonScraper
from scraper.base import OfertaCapturada, Scraper
from scraper.mercadolivre import MercadoLivreScraper

FONTES: list[Scraper] = [
    MercadoLivreScraper(),
    AmazonScraper(),
]

__all__ = ["FONTES", "Scraper", "OfertaCapturada"]
