# Bot de Ofertas → WhatsApp

Monitora ofertas (Pelando, Mercado Livre, Amazon, Magalu), filtra pelos seus
critérios, evita duplicidade e envia automaticamente para um grupo do
WhatsApp via [evolution-api](https://github.com/EvolutionAPI/evolution-api).

## Como rodar

### 1. Suba a evolution-api (WhatsApp)

A API oficial do WhatsApp (Meta Cloud API) **não permite enviar para grupos**,
só conversas 1:1 com opt-in — por isso o envio usa evolution-api, que fala o
protocolo do WhatsApp Web, é gratuita, self-hosted e suporta grupos.

```bash
docker run -d --name evolution-api -p 8080:8080 atendai/evolution-api
```

Depois:
1. Crie uma instância e escaneie o QR Code com o WhatsApp do número que vai enviar as ofertas (`POST /instance/create`, docs da evolution-api).
2. Descubra o ID do grupo de destino (algo como `120363xxxxxx@g.us`) — a própria API lista os grupos em `GET /group/fetchAllGroups/{instance}`.

### 2. Configure o bot

```bash
cd ofertas-bot
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # edite com suas credenciais
```

Preencha no `.env`:
- `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`, `WHATSAPP_GROUP_ID`
- `MERCADOLIVRE_APP_ID` / `MERCADOLIVRE_APP_SECRET` (opcional, mas recomendado — veja abaixo)

Ajuste os critérios de filtro em `config.json` (preço, desconto mínimo, lojas, categorias, palavras-chave, limites de envio).

### 3. Rode

```bash
python main.py
```

O bot já roda a primeira verificação imediatamente e depois a cada
`CHECK_INTERVAL` segundos (padrão 60s), em loop, com logs no console e em
`logs/bot.log`.

## Sobre as fontes de ofertas

| Fonte | Método | Situação |
|---|---|---|
| **Pelando** | scraping de `/mais-quentes` | Funciona sem configuração. Não expõe preço anterior/desconto — para essas ofertas passarem no filtro, deixe `desconto_minimo: 0` ou aceite que só nome/preço/loja sejam usados. |
| **Mercado Livre** | API oficial (`/sites/MLB/search`) | Desde 2026 a ML exige um app registrado — crie um em https://developers.mercadolivre.com.br/ e preencha `MERCADOLIVRE_APP_ID`/`MERCADOLIVRE_APP_SECRET`. Sem isso, a fonte é pulada (log de aviso, o bot continua normalmente). |
| **Amazon** | scraping de `/s?k=` | Amazon bloqueia agressivamente requisições automatizadas (mais do que as outras fontes). Pode funcionar bem de uma rede residencial e falhar de tempos em tempos — isso é esperado para scraping não-oficial; o bot loga o erro e segue sem travar. |
| **Magalu** | scraping do JSON embutido na página de busca | Mesma observação da Amazon: sujeito a bloqueio/mudança de layout. |

Todas as fontes de scraping HTML (Amazon, Magalu, Pelando) dependem da
estrutura atual das páginas. Se um site mudar o layout e uma fonte parar de
retornar ofertas, ajuste **só** o arquivo daquela fonte em `scraper/` — o
resto do pipeline (filtros, dedup, formatação, envio) não muda. Cada fonte
roda isolada: se uma cair, as outras continuam.

## Adicionando uma nova fonte

Crie `scraper/minha_fonte.py` com uma subclasse de `Scraper` (veja
`scraper/base.py`) implementando `buscar() -> list[OfertaCapturada]`, e
adicione uma instância em `scraper/__init__.py`.

## Estrutura

```
ofertas-bot/
├── main.py          # entrypoint, agenda o loop (APScheduler)
├── monitor.py        # um ciclo completo: busca → filtra → dedup → envia
├── scraper/           # uma fonte por arquivo
├── filters.py         # aplica os critérios de config.json
├── dedup.py            # evita reenviar a mesma oferta (permite reenvio se o preço cair)
├── formatter.py        # monta a mensagem a partir do template configurável
├── whatsapp.py          # envio via evolution-api
├── database.py           # SQLite via SQLAlchemy (ofertas + envios)
├── config.py / config.json / .env
└── logs/bot.log
```
