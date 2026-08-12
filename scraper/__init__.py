"""Registro de fontes de ofertas. Para adicionar uma nova fonte, crie um
arquivo com uma subclasse de `Scraper` e adicione uma instância à lista abaixo."""
from scraper.amazon import AmazonScraper
from scraper.base import OfertaCapturada, Scraper
from scraper.magalu import MagaluScraper
from scraper.mercadolivre import MercadoLivreScraper
from scraper.pelando import PelandoScraper

FONTES: list[Scraper] = [
    PelandoScraper(),
    MercadoLivreScraper(),
    AmazonScraper(),
    MagaluScraper(),
]

__all__ = ["FONTES", "Scraper", "OfertaCapturada"]
