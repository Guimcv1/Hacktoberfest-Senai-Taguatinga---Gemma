# Hacktoberfest-Senai-Taguatinga---Gemma

## Equipe

- Humberto Gabriel Bezerra de Oliveira - humbertobezerradeoliveira@gmail.com
- Guilherme Martins Coelho Vilmar
- Arthur Nunes de Carvalho

Esta branch (`backend`) contém a API Python do **StudyBuddy AI**.

# StudyBuddy AI — Backend

API do professor virtual: o estudante autentica e conversa com **Gemma 3:4b via Ollama**. O PDF é **opcional** — só precisa ser enviado quando a pergunta deve se apoiar naquele material. A URL da IA fica só no servidor.

## Arquitetura

```text
Frontend  --CORS-->  FastAPI
                      ├─ JWT (cadastro/login/logout)
                      ├─ SQLite (dev) ou PostgreSQL
                      ├─ extração PyMuPDF + retrieval lexical (só PDFs da conversa)
                      └─ AIClient --> Ollama / Gemma 3:4b
```

- Não há um agente em memória por usuário. Cada pergunta é um `POST {AI_BASE_URL}/api/chat`.
- O histórico da conversa é persistido no banco e reenviado ao Gemma nas próximas mensagens (até `MAX_CONTEXT_CHARS`).
- O Ollama descarrega o modelo da RAM após **120 segundos** sem novas chamadas (`OLLAMA_KEEP_ALIVE=120s`).
- Documentos, conversas e usuários são **isolados por conta**.
- OCR **não** está implementado. PDF só com imagem é rejeitado.
- Tokens JWT de acesso (8 h por padrão), com logout por denylist. **Não há refresh token**.

## Fluxo para o frontend

1. Cadastre/login → guarde `access_token` → envie `Authorization: Bearer <token>`.
2. **Chat imediato, sem PDF:** `POST /api/chat` com `{"message": "..."}`. A API cria a conversa.
3. **Continuar a conversa:** envie o `conversation_id` retornado. O histórico vai para o modelo.
4. **Estudar um PDF (opcional):**
   - `POST /api/documents` (campo `file`) e depois `POST /api/conversations/{id}/documents` com `{"document_id": "..."}`; ou
   - `POST /api/documents` com `file` + `conversation_id` (form); ou
   - incluir `document_id` no `POST /api/chat` (associa aquele PDF à conversa).
5. Mensagens seguintes usam **apenas** os PDFs associados àquela conversa. Outros arquivos do usuário não entram no contexto.
6. Não use a URL do Ollama no browser. Configure `CORS_ORIGINS`.

### Mudança de contrato

| Campo | Antes | Agora |
| --- | --- | --- |
| `POST /api/chat` `document_id` | obrigatório | **opcional** |
| `POST /api/conversations` `document_id` | obrigatório | **opcional** (body `{}` cria conversa vazia) |
| Resposta `document_id` | sempre string | `null` se não houver PDF |
| Resposta `document_ids` | — | lista dos PDFs da conversa |
| Resposta `used_documents` | — | se a recuperação documental rodou |
| `sources` | páginas recuperadas, inclusive fallback | só trechos com correspondência lexical; vazio se não houver suporte no PDF |
| `POST /api/conversations/{id}/documents` | — | anexa um PDF já enviado |

Clientes antigos que ainda enviam `document_id` no chat continuam funcionando.

## Endpoints

| Método | Caminho | Auth | Função |
| --- | --- | --- | --- |
| GET | `/health` | não | liveness da API |
| GET | `/ready` | não | banco + se a IA está configurada |
| POST | `/api/auth/register` | não | cadastro + token |
| POST | `/api/auth/login` | não | login |
| POST | `/api/auth/logout` | sim | invalida o token atual |
| GET | `/api/auth/me` | sim | perfil |
| POST | `/api/documents` | sim | upload PDF (`file`, opcional `conversation_id`) |
| GET | `/api/documents` | sim | listagem paginada |
| GET | `/api/documents/{id}` | sim | metadados + páginas |
| DELETE | `/api/documents/{id}` | sim | exclusão (a conversa permanece) |
| POST | `/api/chat` | sim | pergunta (cria conversa se omitido `conversation_id`) |
| POST | `/api/conversations` | sim | cria conversa, com ou sem PDF |
| GET | `/api/conversations` | sim | listagem |
| GET | `/api/conversations/{id}` | sim | histórico |
| POST | `/api/conversations/{id}/documents` | sim | anexa PDF existente |
| DELETE | `/api/conversations/{id}` | sim | apaga a conversa |
| DELETE | `/api/conversations/{id}/messages` | sim | limpa mensagens |

### Chat (200)

Pedido mínimo:

```json
{ "message": "O que é mitose?" }
```

Com conversa e PDF:

```json
{
  "message": "Explique o conceito principal",
  "conversation_id": "uuid",
  "document_id": "uuid"
}
```

Resposta:

```json
{
  "conversation_id": "uuid",
  "document_id": "uuid-ou-null",
  "document_ids": ["uuid"],
  "answer": "Explicação",
  "sources": [{"page": 2, "excerpt": "trecho real", "document_id": "uuid", "filename": "aula.pdf"}],
  "model": "gemma3:4b",
  "status": "completed",
  "has_relevant_match": true,
  "used_documents": true
}
```

- Sem PDF: `sources` é `[]`, `used_documents` é `false`. O Gemma responde com conhecimento geral e o histórico.
- Com PDF e trechos relevantes: `sources` traz páginas reais do arquivo associado.
- Com PDF sem correspondência: `has_relevant_match` é `false`, `sources` é `[]`. O modelo é instruído a dizer que o material não deu suporte suficiente e pode completar com conhecimento geral, sem fingir citação.

O texto extraído do PDF é persistido uma vez no upload; as mensagens seguintes não reprocessam o arquivo.

## Recuperação documental

- Lexical (sem embeddings). Só os documentos **da conversa atual**.
- O texto já extraído em `pages_json` é reutilizado.
- Limites: `MAX_RETRIEVAL_PAGES`, `MAX_CONTEXT_CHARS`.

## Ollama e memória do modelo

O cliente envia `keep_alive` em cada `POST /api/chat` ao Ollama. Padrão: `120s`.

| Variável | Função |
| --- | --- |
| `AI_BASE_URL` | URL do Ollama, só no backend |
| `AI_MODEL` | `gemma3:4b` |
| `AI_TIMEOUT_SECONDS` | timeout HTTP da inferência |
| `OLLAMA_KEEP_ALIVE` | quanto tempo o modelo fica carregado (`120s`, `2m`, `0` ou `-1`) |

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

## Banco

Dev (padrão): SQLite. A API aplica as migrações Alembic na inicialização (`DB_AUTO_MIGRATE=true`).

PostgreSQL opcional:

```bash
docker compose up -d postgres
# DATABASE_URL=postgresql+psycopg2://studybuddy:studybuddy@localhost:5432/studybuddy
alembic upgrade head
```

`JWT_SECRET` precisa estar definido para a API carregar. O Alembic usa só `DATABASE_URL`.

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
- O histórico enviado ao modelo é truncado por `MAX_CONTEXT_CHARS`; mensagens antigas podem ficar de fora do prompt, mas permanecem no banco.
