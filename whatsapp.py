"""Envio de mensagens para o grupo do WhatsApp via evolution-api (self-hosted).

evolution-api expõe uma API REST simples sobre o protocolo do WhatsApp Web —
é gratuita, roda em Docker e suporta envio para grupos, o que a API oficial
(Meta Cloud API) NÃO suporta. Ver README.md para instruções de setup.
"""
from __future__ import annotations

import httpx

from config import settings
from logger import logger


class WhatsAppError(Exception):
    pass


def enviar_mensagem(texto: str, imagem: str | None = None) -> bool:
    """Envia `texto` (com `imagem` opcional) para o grupo configurado.
    Retorna True em sucesso, False em falha (nunca lança para não parar o bot)."""

    if not settings.evolution_instance or not settings.whatsapp_group_id:
        logger.error("WhatsApp não configurado: defina EVOLUTION_INSTANCE e WHATSAPP_GROUP_ID no .env")
        return False

    headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=15.0) as client:
            if imagem:
                url = f"{settings.evolution_api_url}/message/sendMedia/{settings.evolution_instance}"
                payload = {
                    "number": settings.whatsapp_group_id,
                    "mediatype": "image",
                    "media": imagem,
                    "caption": texto,
                }
            else:
                url = f"{settings.evolution_api_url}/message/sendText/{settings.evolution_instance}"
                payload = {"number": settings.whatsapp_group_id, "text": texto}

            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            logger.error(f"evolution-api retornou erro {resp.status_code}: {resp.text[:300]}")
            return False

        return True

    except httpx.RequestError as e:
        logger.error(f"Falha ao conectar na evolution-api ({settings.evolution_api_url}): {e}")
        return False
