# Hacktoberfest-Senai-Taguatinga---Gemma

## Equipe

- Humberto Gabriel Bezerra de Oliveira - humbertobezerradeoliveira@gmail.com
- Guilherme Martins Coelho Vilmar
- Arthur Nunes de Carvalho

Esta branch (`backend`) contém a API Python do **StudyBuddy AI**.

# StudyBuddy AI — Backend

API do professor virtual: o estudante autentica, envia um PDF e pergunta sobre o material. O backend recupera páginas reais e consulta **Gemma 3:4b via Ollama**. A URL da IA fica só no servidor.

## Arquitetura

```text
Frontend  --CORS-->  FastAPI
                      ├─ JWT (cadastro/login/logout)
                      ├─ SQLite (dev) ou PostgreSQL
                      ├─ extração PyMuPDF + retrieval lexical
                      └─ AIClient --> Ollama / Gemma 3:4b
```

- O backend não guarda um agente em memória por usuário. Cada pergunta é um `POST {AI_BASE_URL}/api/chat` sem sessão no Ollama.
- O Ollama descarrega o modelo da RAM após **120 segundos** sem novas chamadas (`OLLAMA_KEEP_ALIVE=120s`). O processo do Ollama continua no ar; conversas e documentos no banco não são apagados.
- Documentos, conversas e usuários são **isolados por conta**.
- Persistência padrão: SQLite em `data/studybuddy.db` (sobrevive a restart).
- PostgreSQL é opcional via `DATABASE_URL`.
- Store em memória antigo permanece só como utilitário de testes unitários; a API usa o banco.
- OCR **não** está implementado. PDF só com imagem é rejeitado.
- Tokens JWT de acesso (8 h por padrão), com logout por denylist. **Não há refresh token** nesta versão: o frontend deve pedir login de novo após expirar ou logout.

## Endpoints

| Método | Caminho | Auth | Função |
| --- | --- | --- | --- |
| GET | `/health` | não | liveness da API |
| GET | `/ready` | não | banco + se a IA está configurada |
| POST | `/api/auth/register` | não | cadastro + token |
| POST | `/api/auth/login` | não | login |
| POST | `/api/auth/logout` | sim | invalida o token atual |
| GET | `/api/auth/me` | sim | perfil |
| POST | `/api/documents` | sim | upload PDF |
| GET | `/api/documents` | sim | listagem paginada |
| GET | `/api/documents/{id}` | sim | metadados + páginas |
| DELETE | `/api/documents/{id}` | sim | exclusão |
| POST | `/api/chat` | sim | pergunta (cria conversa se omitido `conversation_id`) |
| GET/POST/DELETE | `/api/conversations` | sim | histórico |

Auth: header `Authorization: Bearer <token>`.

### Upload (201)

Campo `file` em `multipart/form-data`. Resposta inclui `document_id`, `filename`, `page_count`, `pages`, `deduplicated`.

### Chat (200)

```json
{
  "document_id": "uuid",
  "conversation_id": "uuid",
  "message": "Explique o conceito principal"
}
```

Resposta:

```json
{
  "document_id": "uuid",
  "conversation_id": "uuid",
  "answer": "Explicação",
  "sources": [{"page": 2, "excerpt": "trecho real"}],
  "model": "gemma3:4b",
  "status": "completed",
  "has_relevant_match": true
}
```

`sources` vêm das páginas recuperadas pelo backend, não do modelo. `status` hoje é `completed` em sucesso; erros usam HTTP 502/503. Estados `thinking`/`answering` ficam para streaming futuro.

## Integração com o frontend

1. Não use a URL do Ollama no browser.
2. Configure `CORS_ORIGINS` com a origem da UI.
3. Cadastre/login → guarde `access_token` → envie Bearer em todas as rotas privadas.
4. Upload → `document_id` → chat. Opcional: reutilizar `conversation_id`.
5. **Mudança de contrato:** upload e chat agora exigem autenticação.

## Instalação

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edite JWT_SECRET em .env
uvicorn app.main:app --reload
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## Ollama e memória do modelo

O cliente de IA envia `keep_alive` no corpo de cada `POST /api/chat` (contrato do Ollama). Padrão: `120s`.

| Variável | Função |
| --- | --- |
| `AI_BASE_URL` | URL do Ollama, só no backend |
| `AI_MODEL` | `gemma3:4b` |
| `AI_TIMEOUT_SECONDS` | timeout HTTP da inferência |
| `OLLAMA_KEEP_ALIVE` | quanto tempo o modelo fica carregado após a última resposta (`120s`, `2m`, `0` ou `-1`) |

O temporizador é do próprio Ollama: uma nova pergunta válida o reinicia; requisições ainda em andamento não são canceladas. Se o modelo já tiver saído da memória, a próxima pergunta o recarrega (pode demorar mais). Isso não encerra o servidor Ollama e não apaga histórico persistido.

## Banco

Dev (padrão): SQLite. A API cria as tabelas na inicialização.

PostgreSQL opcional:

```bash
docker compose up -d postgres
# DATABASE_URL=postgresql+psycopg2://studybuddy:studybuddy@localhost:5432/studybuddy
alembic upgrade head
```

`JWT_SECRET` precisa estar definido para o Alembic/Settings carregarem.

## Testes

```bash
pytest
```

A suíte usa SQLite em memória e **mock da IA**. Não depende do túnel.

## Limitações

- Prompt injection em PDFs não pode ser eliminada por completo; o conteúdo é tratado como material de estudo, não como instrução de sistema.
- Sem OCR, embeddings, avatar, voz ou S3/MinIO (arquivos originais não são gravados; só o texto extraído).
- Rate limit em memória por processo; não compartilha entre workers.
- JWT sem refresh; logout só invalida o `jti` apresentado.
