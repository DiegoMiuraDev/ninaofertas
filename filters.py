"""Aplica os critérios de `config.json` sobre uma oferta capturada."""
from __future__ import annotations

from scraper.base import OfertaCapturada


def _contem_alguma(texto: str, termos: list[str]) -> bool:
    texto_lower = texto.lower()
    return any(termo.lower() in texto_lower for termo in termos)


def passa_nos_filtros(oferta: OfertaCapturada, filtros: dict) -> tuple[bool, str]:
    """Retorna (passou, motivo). `motivo` é usado apenas para log quando falha."""

    preco_maximo = filtros.get("preco_maximo")
    if preco_maximo and oferta.preco > preco_maximo:
        return False, f"preço R${oferta.preco:.2f} acima do máximo R${preco_maximo:.2f}"

    preco_minimo = filtros.get("preco_minimo")
    if preco_minimo and oferta.preco < preco_minimo:
        return False, f"preço R${oferta.preco:.2f} abaixo do mínimo R${preco_minimo:.2f}"

    desconto_minimo = filtros.get("desconto_minimo")
    if desconto_minimo:
        if oferta.desconto is None:
            return False, "desconto desconhecido (não foi possível confirmar preço anterior)"
        if oferta.desconto < desconto_minimo:
            return False, f"desconto {oferta.desconto}% abaixo do mínimo {desconto_minimo}%"

    lojas = filtros.get("lojas")
    if lojas and oferta.loja and oferta.loja.lower() not in [l.lower() for l in lojas]:
        return False, f"loja '{oferta.loja}' não está na lista permitida"

    # Categoria só é aplicada quando a fonte informa esse dado; a maioria dos
    # scrapers via HTML não consegue extrair categoria com confiança.
    categorias = filtros.get("categorias")
    if categorias and oferta.categoria and not _contem_alguma(oferta.categoria, categorias):
        return False, f"categoria '{oferta.categoria}' não está na lista permitida"

    palavras_chave = filtros.get("palavras_chave")
    if palavras_chave and not _contem_alguma(oferta.nome, palavras_chave):
        return False, "nome não contém nenhuma palavra-chave configurada"

    produtos_especificos = filtros.get("produtos_especificos")
    if produtos_especificos and not _contem_alguma(oferta.nome, produtos_especificos):
        return False, "não corresponde a nenhum produto específico monitorado"

    return True, ""
