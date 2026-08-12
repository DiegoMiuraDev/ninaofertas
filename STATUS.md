# Status do projeto — onde paramos

Última atualização: 2026-08-12

## ✅ O que já está pronto (feito e testado)

O bot inteiro já está implementado em `ofertas-bot/` e funcionando:

- `main.py`, `monitor.py`, `filters.py`, `dedup.py`, `formatter.py`, `whatsapp.py`, `database.py`, `logger.py`, `config.py` — tudo escrito e testado rodando de verdade.
- 4 fontes de ofertas em `scraper/`: Pelando (funcionando, testado com dados reais), Mercado Livre (código pronto, falta credencial — ver abaixo), Amazon e Magalu (código pronto, sujeitas a bloqueio anti-bot, isso é normal).
- Banco SQLite, dedup (evita reenvio, mas reenvia se o preço cair), formatação de mensagem — tudo validado com testes ponta a ponta.
- Venv Python já criado em `ofertas-bot/venv/` com todas as dependências instaladas. Não precisa reinstalar nada.
- `.env` já existe (copiado do `.env.example`), mas com valores de placeholder — falta preencher os de WhatsApp.

Detalhes técnicos completos estão no `README.md` da pasta.

## 🔧 Onde paramos agora (em andamento)

Estamos configurando o **envio real pro WhatsApp**, que depende da **evolution-api** rodando via Docker.

Passo a passo do que falta:

1. ~~Instalar Docker Desktop~~ ✅ feito
2. **🔴 VOCÊ ESTÁ AQUI:** Docker deu erro "Virtualization support not detected" ao abrir.
   - Diagnosticamos: virtualização **já está habilitada na BIOS** (confirmado no Gerenciador de Tarefas).
   - Causa real: falta habilitar WSL2 / Virtual Machine Platform no Windows.
   - Você rodou (ou está rodando) como Administrador no PowerShell:
     ```powershell
     wsl --install --no-distribution
     # (ou wsl --update se já tinha WSL)
     dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
     dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
     ```
   - **Próxima ação: reiniciar o PC** (obrigatório) e depois abrir o Docker Desktop de novo pra ver se o erro sumiu (ícone verde "Engine running").

3. Depois que o Docker abrir certo, os próximos passos (ainda não feitos):
   - Subir o container da evolution-api:
     ```
     docker run -d --name evolution-api -p 8080:8080 atendai/evolution-api
     ```
   - Criar uma instância via API da evolution-api.
   - Escanear o QR Code com o WhatsApp que vai enviar as ofertas (Configurações → Aparelhos conectados → Conectar aparelho).
   - Listar os grupos desse WhatsApp e identificar o ID do grupo de ofertas (formato `120363xxxxxx@g.us`).
   - Preencher no `.env`: `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`, `WHATSAPP_GROUP_ID`.
   - Rodar `python main.py` e ver a primeira oferta real chegando no grupo.

4. Opcional, depois que o WhatsApp estiver funcionando:
   - Criar app gratuito em https://developers.mercadolivre.com.br/ e preencher `MERCADOLIVRE_APP_ID`/`MERCADOLIVRE_APP_SECRET` no `.env`, pra ativar a fonte Mercado Livre (hoje pulada por falta de credencial).
   - Ajustar `config.json` com os filtros que você realmente quer (categorias, preço, desconto mínimo, lojas).

## Como retomar numa conversa nova

Se essa conversa se perder, é só abrir uma nova e falar algo como:
> "Continua o setup do bot de ofertas, olha o STATUS.md na pasta ofertas-bot"

E colar/apontar esse arquivo.
