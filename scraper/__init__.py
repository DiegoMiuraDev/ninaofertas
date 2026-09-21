"""Registro de fontes de ofertas.

Foco do canal: Mercado Livre + Shopee (produtos, promoções e cupons),
sempre com link de afiliado quando possível.
"""
from scraper.base import OfertaCapturada, Scraper
from scraper.cupons import CupomScraper
from scraper.mercadolivre import MercadoLivreScraper
from scraper.shopee import ShopeeScraper

FONTES: list[Scraper] = [
    CupomScraper(),
    MercadoLivreScraper(),
    ShopeeScraper(),
]

__all__ = ["FONTES", "Scraper", "OfertaCapturada"]
