# Hacktoberfest-Senai-Taguatinga---Gemma

## Equipe

- Humberto Gabriel Bezerra de Oliveira - humbertobezerradeoliveira@gmail.com
- Guilherme Martins Coelho Vilmar
- Arthur Nunes de Carvalho

Esta branch (`backend`) contém a API Python do **StudyBuddy AI**.

# StudyBuddy AI — Backend

API do professor virtual: o estudante autentica e conversa com **Gemma 4 E4B (`gemma4:e4b`) via Ollama**. O PDF é **opcional** — só precisa ser enviado quando a pergunta deve se apoiar naquele material. A URL da IA fica só no servidor.

## Arquitetura

```text
Frontend  --CORS-->  FastAPI
                      ├─ JWT (cadastro/login/logout)
                      ├─ SQLite (dev) ou PostgreSQL
                      ├─ extração PyMuPDF + retrieval lexical (só PDFs da conversa)
                      └─ AIClient --> Ollama / Gemma 4 E4B (`gemma4:e4b`)
```

- Não há um agente em memória por usuário. Cada pergunta é um `POST {AI_BASE_URL}/api/chat`.
- O histórico da conversa é persistido no banco e reenviado ao Gemma nas próximas mensagens (até `MAX_CONTEXT_CHARS`).
- O Ollama descarrega o modelo da RAM após **120 segundos** sem novas chamadas (`OLLAMA_KEEP_ALIVE=120s`). Também há unload manual autenticado (`POST /api/ai/unload`).
- Documentos, conversas e usuários são **isolados por conta**.
- OCR **não** está implementado. PDF só com imagem é rejeitado.
- Tokens JWT de acesso (8 h por padrão), com logout por denylist. **Não há refresh token**.

## Fluxo para o frontend

Não há dependência circular: conversa e PDF são independentes.

1. Cadastre/login → guarde `access_token` → `Authorization: Bearer <token>`.
2. **Criar conversa sem PDF:** `POST /api/conversations` com `{}`, `null` ou **sem corpo**. Não envie `document_id`.
3. **Perguntar sem PDF:** `POST /api/chat` `{"conversation_id": "<id>", "message": "..."}`. Também vale omitir `conversation_id` e deixar a API criar a conversa.
4. **Upload opcional, sem conversa:** `POST /api/documents` só com o campo `file`. **Não envie `conversation_id`.** O PDF fica persistido (texto extraído) e não cria conversa.
5. **Associar depois:** `POST /api/conversations/{id}/documents` `{"document_id": "<id>"}`.
6. **Perguntar de novo** no mesmo `conversation_id`: a recuperação usa só os PDFs dessa conversa.
7. Atalhos compatíveis (não obrigatórios): `document_id` no chat, ou `conversation_id` no form do upload, se a conversa já existir e for do mesmo usuário.
8. **Gerar questões da conversa selecionada:** `POST /api/conversations/{id}/questions/generate` com `{}` ou preferências (`observation`, `quantity`, `difficulty`). Mostre loading; a inferência pode levar dezenas de segundos.
9. **Relistar sem nova IA:** `GET /api/conversations/{id}/questions`.
10. Não use a URL do Ollama no browser. Configure `CORS_ORIGINS`.

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
| POST | `/api/ai/unload` | sim | descarrega o modelo da memória do Ollama (`keep_alive: 0`) |
| POST | `/api/conversations` | sim | cria conversa, com ou sem PDF |
| GET | `/api/conversations` | sim | listagem |
| GET | `/api/conversations/{id}` | sim | histórico |
| POST | `/api/conversations/{id}/documents` | sim | anexa PDF existente |
| POST | `/api/conversations/{id}/questions/generate` | sim | gera questões (Gemma) e persiste o conjunto |
| GET | `/api/conversations/{id}/questions` | sim | conjuntos já gerados, mais recentes primeiro |
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
  "model": "gemma4:e4b",
  "status": "completed",
  "has_relevant_match": true,
  "used_documents": true
}
```

- Sem PDF: `sources` é `[]`, `used_documents` é `false`. O Gemma responde com conhecimento geral e o histórico.
- Com PDF e trechos relevantes: `sources` traz páginas reais do arquivo associado.
- Com PDF sem correspondência: `has_relevant_match` é `false`, `sources` é `[]`. O modelo é instruído a dizer que o material não deu suporte suficiente e pode completar com conhecimento geral, sem fingir citação.

O texto extraído do PDF é persistido uma vez no upload; as mensagens seguintes não reprocessam o arquivo.

### Geração de questões (201)

Usa a conversa já selecionada: **não** cria outra conversa e **não** exige upload. O histórico da conversa não é alterado.

Pedido (`observation` pode ser omitida, `null` ou `""`):

```json
{
  "observation": "Crie 10 questões difíceis, no estilo ENEM, priorizando os conceitos mais importantes e incluindo explicações detalhadas.",
  "quantity": 10,
  "difficulty": "hard",
  "question_type": "multiple_choice"
}
```

| Campo | Padrão | Limites |
| --- | --- | --- |
| `observation` | ausente | opcional; no máximo 500 caracteres; em branco vira ausente |
| `quantity` | 5 | inteiro de 1 a 10 |
| `difficulty` | `medium` | `easy`, `medium` ou `hard` |
| `question_type` | `multiple_choice` | só múltipla escolha nesta versão |

Resposta:

```json
{
  "id": "uuid-do-conjunto",
  "conversation_id": "uuid",
  "observation": "Crie 10 questões difíceis, estilo ENEM",
  "quantity": 10,
  "difficulty": "hard",
  "question_type": "multiple_choice",
  "questions": [
    {
      "stem": "Enunciado",
      "choices": [
        {"id": "A", "text": "alternativa A"},
        {"id": "B", "text": "alternativa B"},
        {"id": "C", "text": "alternativa C"},
        {"id": "D", "text": "alternativa D"}
      ],
      "correct_option": "A",
      "explanation": "Por que A está correta.",
      "difficulty": "hard"
    }
  ],
  "used_documents": true,
  "has_relevant_match": true,
  "sources": [{"page": 2, "excerpt": "trecho real", "document_id": "uuid", "filename": "aula.pdf"}],
  "model": "gemma4:e4b",
  "created_at": "2026-10-27T12:00:00Z"
}
```

Como o frontend pode renderizar:

1. Botão **Gerar questões** na conversa selecionada; campo opcional de observação.
2. Estado de carregamento até o `201`.
3. Para cada item em `questions`: enunciado (`stem`), alternativas A–D (`choices`), gabarito (`correct_option` — só marcar depois de conferir que existe em `choices`) e `explanation`.
4. Se `used_documents` e `has_relevant_match`, mostrar `sources` (páginas reais). Se `used_documents` e não `has_relevant_match`, avisar que o PDF não teve trechos alinhados e as questões não estão comprovadamente fundamentadas no documento.
5. Sem PDF: `used_documents` é `false` e `sources` é `[]`; as questões vêm do histórico e do conhecimento geral do Gemma.
6. Guardar `id` do conjunto ou reler com `GET /api/conversations/{id}/questions` — **não** é preciso chamar a IA de novo.

Comportamento e erros:

- Sem histórico substancial (cerca de 80 caracteres no total) e sem PDF: `422` “A conversa ainda não tem conteúdo suficiente para gerar questões.”
- Conversa inexistente ou de outra conta: `404`.
- Quantidade, dificuldade ou observação inválidas: `422` com `errors`.
- JSON inválido, alternativas incompletas ou gabarito que não existe: uma tentativa de correção; se falhar, `502`.
- Timeout ou Ollama indisponível: `503`, sem vazar URL nem detalhes internos.
- `sources` vêm só da recuperação lexical do backend. O modelo não inventa páginas na resposta da API.

Os conjuntos ficam na tabela `question_sets`, ligados à conversa e ao usuário. Apagar a conversa remove os conjuntos.

## Recuperação documental

- Lexical (sem embeddings). Só os documentos **da conversa atual**.
- O texto já extraído em `pages_json` é reutilizado.
- Limites: `MAX_RETRIEVAL_PAGES`, `MAX_CONTEXT_CHARS`.

## Ollama e memória do modelo

O cliente envia `keep_alive` em cada `POST /api/chat` ao Ollama (chat e geração de questões). Padrão: `120s`. A geração pede `format: json` nesse mesmo contrato.

A tag padrão é **`gemma4:e4b`**, a variante E4B da biblioteca oficial do Ollama (`gemma4:latest` é um alias; `gemma4` sem tag e `gemma3:4b` **não** são equivalentes). Instale no host do Ollama:

```bash
ollama pull gemma4:e4b
```

A API **não** baixa nem instala o modelo na inicialização. Se `AI_MODEL` apontar para uma tag que o Ollama ainda não tem, as inferências falham com 503.

### Descarregar o modelo (`POST /api/ai/unload`)

Pedido autenticado, sem corpo. A API envia ao Ollama:

```json
{ "model": "gemma4:e4b", "prompt": "", "stream": false, "keep_alive": 0 }
```

em `POST {AI_BASE_URL}/api/generate`. Não usa `ollama rm`, `/api/delete`, `/api/pull` nem `/api/stop`.

Resposta `200`:

```json
{
  "status": "unloaded",
  "model": "gemma4:e4b",
  "message": "O Ollama aceitou o pedido para descarregar o modelo da memória. A próxima pergunta pode carregá-lo de novo. Isso não apaga o modelo nem mede a RAM ou a VRAM liberada."
}
```

- `409` se já houver inferência (chat ou questões) em andamento neste processo.
- `503` se o Ollama não responder, estourar timeout ou recusar o unload. O backend **não** trata erro do Ollama como sucesso.
- Durante o unload, novas inferências neste processo recebem `503`.
- O cadeado é **por processo**. Vários workers Uvicorn ou várias instâncias da API não compartilham esse estado: descarregue só com um worker, ou quando não houver carga. Não medimos RAM/VRAM física.
- A próxima pergunta recarrega o modelo normalmente (o Ollama faz o load sob demanda).

| Variável | Função |
| --- | --- |
| `AI_BASE_URL` | URL do Ollama, só no backend |
| `AI_MODEL` | `gemma4:e4b` (configurável) |
| `AI_TIMEOUT_SECONDS` | timeout HTTP da inferência (padrão 120; a primeira carga após unload pode chegar perto desse limite) |
| `OLLAMA_KEEP_ALIVE` | quanto tempo o modelo fica carregado (`120s`, `2m`, `0` ou `-1`) |

## Instalação

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edite JWT_SECRET e, se o Ollama estiver em outro host, AI_BASE_URL
# no host do Ollama: ollama pull gemma4:e4b
uvicorn app.main:app --reload
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ollama pull gemma4:e4b
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
- A qualidade pedagógica das questões depende do Gemma 4 E4B; a suíte de testes usa mock da IA e não valida o modelo real.
- O unload manual só coordena inferências **neste processo**. Com vários workers, um unload pode coincidir com uma inferência em outro worker.
- Só há múltipla escolha (A–D) nesta versão; outros tipos de questão ainda não estão implementados.
