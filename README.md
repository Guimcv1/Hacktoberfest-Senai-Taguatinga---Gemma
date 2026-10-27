# Hacktoberfest-Senai-Taguatinga---Gemma

## Equipe

- Humberto Gabriel Bezerra de Oliveira - humbertobezerradeoliveira@gmail.com
- Guilherme Martins Coelho Vilmar
- Arthur Nunes de Carvalho

Esta branch (`backend`) contém a API Python do **StudyBuddy AI**.

# StudyBuddy AI — Backend

Backend da plataforma de estudos: o estudante envia um PDF, pergunta sobre o conteúdo e recebe explicações de um professor virtual.

O serviço de IA é acessado **somente pelo backend**. A URL do modelo não deve ir para o frontend.

## Escopo atual

- `GET /health` — estado de saúde do backend
- `POST /api/documents` — upload de PDF, extração por página e registro temporário em memória
- `POST /api/chat` — pergunta sobre um documento já enviado
- Recuperação lexical de páginas relevantes
- Integração com `POST {AI_BASE_URL}/api/chat` e o modelo `gemma3:4b`

## Fora desta etapa

- Banco de dados, autenticação e contas
- Embeddings, banco vetorial e OCR
- Interface, avatar e voz

## Requisitos

- Python 3.12 ou superior (verificado com Python 3.13)
- Ambiente virtual Python

## Instalação

No Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Se o comando `python` não estiver no PATH, use o executável completo da instalação local.

## Configuração

As variáveis ficam em `.env`. Use `.env.example` como modelo. Não versione credenciais reais.

| Variável | Função |
| --- | --- |
| `AI_BASE_URL` | URL base do serviço de IA, usada só no backend |
| `AI_MODEL` | Nome do modelo (`gemma3:4b`) |
| `AI_TIMEOUT_SECONDS` | Timeout das chamadas à IA |
| `MAX_PDF_SIZE_MB` | Limite de upload de PDF, em megabytes |
| `DOCUMENT_TTL_MINUTES` | Tempo de vida dos documentos em memória |
| `MAX_STORED_DOCUMENTS` | Quantidade máxima de documentos simultâneos |
| `MAX_STORED_TEXT_CHARS` | Tamanho máximo total do texto armazenado |
| `MAX_CHAT_MESSAGE_CHARS` | Tamanho máximo da pergunta |
| `MAX_RETRIEVAL_PAGES` | Páginas enviadas como contexto |
| `MAX_CONTEXT_CHARS` | Limite de caracteres do contexto |

Os documentos ficam só em memória. **Eles são perdidos quando o processo reinicia** e deixam de ser acessíveis após o TTL (padrão 30 minutos).

## Execução

Na raiz do projeto, com o ambiente virtual ativo:

```bash
uvicorn app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- Upload: `http://127.0.0.1:8000/api/documents`
- Chat: `http://127.0.0.1:8000/api/chat`
- Swagger: `http://127.0.0.1:8000/docs`

## `POST /api/documents`

Campo `file` em `multipart/form-data`. O backend valida o conteúdo do PDF, extrai o texto por página e guarda o resultado em memória.

Sucesso — HTTP 201:

```json
{
  "document_id": "identificador-uuid",
  "filename": "material.pdf",
  "page_count": 2,
  "pages": [
    {"page_number": 1, "text": "Texto extraído da primeira página"},
    {"page_number": 2, "text": "Texto extraído da segunda página"}
  ]
}
```

O `document_id` é o identificador usado depois em `/api/chat`.

## `POST /api/chat`

```json
{
  "document_id": "id-retornado-no-upload",
  "message": "Explique o conceito principal deste capítulo"
}
```

Sucesso — HTTP 200:

```json
{
  "document_id": "id-do-documento",
  "answer": "Explicação produzida pelo professor",
  "sources": [
    {"page": 3, "excerpt": "Trecho real extraído do documento"}
  ],
  "model": "gemma3:4b"
}
```

As fontes são montadas pelo backend a partir das páginas recuperadas. Números de página gerados pelo modelo são ignorados.

| HTTP | Situação |
| --- | --- |
| 404 | Documento inexistente ou expirado |
| 422 | Mensagem vazia ou grande demais |
| 502 | Resposta inválida da IA |
| 503 | IA indisponível ou em timeout |

## Testes

```bash
pytest
```

A suíte usa mocks para a IA e **não depende** do túnel público.

## Limitações conhecidas

- Sem login: quem tiver o `document_id` acessa o documento até expirar.
- Sem banco: os dados somem ao reiniciar o processo.
- A URL da IA fica só em variável de ambiente (`AI_BASE_URL`), nunca no frontend.
- PDFs sem texto extraível (somente imagem) não são suportados nesta etapa.

## Estrutura

```text
app/
  main.py
  api/routes/             # health, documents, chat
  core/config.py
  schemas/
  services/documents.py   # extração de PDFs
  services/document_store.py  # memória temporária
  services/retrieval.py   # seleção lexical de páginas
  services/ai_client.py   # POST /api/chat
tests/
```
