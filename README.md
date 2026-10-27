# Hacktoberfest-Senai-Taguatinga---Gemma

# Equipe :

- Humberto Gabriel Bezerra de Oliveira - humbertobezerradeoliveira@gmail.com
- Guilherme Martins Coelho Vilmar - guimcvilmar@gmail.com
- Arthur Nunes de Carvalho - arthurnunescarvalho2@gmail.com

<<<<<<< HEAD
## Executar com Docker Compose

A aplicação completa é orquestrada pelo [`compose.yaml`](./compose.yaml). O frontend
é o único serviço exposto ao host; ele encaminha `/api` para o backend pela rede
interna do Docker. PostgreSQL, Ollama e backend não publicam portas.

1. Copie `.env.example` para `.env` e altere `JWT_SECRET` e `POSTGRES_PASSWORD`.
2. Baixe o modelo no Ollama:

   ```powershell
   docker compose run --rm ollama ollama pull gemma4:e4b
   ```

3. Suba os serviços:

   ```powershell
   docker compose up --build -d
   ```

4. Acesse `http://localhost:8080` (ou a porta definida em `APP_PORT`).

Para acompanhar a inicialização:

```powershell
docker compose logs -f backend frontend
```
=======
## Frontend (desenvolvimento)

```bash
cd frontend
npm install
npm run dev
```

O Vite encaminha `/api`, `/health` e `/ready` para `http://127.0.0.1:8000`. Deixe `VITE_API_URL` vazio. Não use o hostname interno `backend` no navegador.

## Implantação Docker

Os arquivos de Compose **não foram executados nesta máquina** (Docker não está instalado). A implantação precisa ser validada no servidor de destino.

O código do backend vive na branch `backend`; o do frontend, nesta branch (`frontend/`). O `docker-compose.yml` constrói cada serviço a partir do GitHub:

- backend: `...Gemma.git#backend`
- frontend: `...Gemma.git#frontend:frontend`

Assim não é necessário ter as duas árvores no mesmo checkout. O servidor precisa clonar o repositório durante o `docker compose build`. A branch `main` não é usada.

Neste checkout da branch `frontend`, para construir a UI localmente:

```bash
BACKEND_CONTEXT=https://github.com/Guimcv1/Hacktoberfest-Senai-Taguatinga---Gemma.git#backend
FRONTEND_CONTEXT=./frontend
```

Não use `docker compose down -v` na atualização normal.

### Arquitetura

```text
navegador --> :8080 frontend (Nginx)
                 ├─ /        UI
                 └─ /api     proxy --> backend:8000 (1 worker)
                                    ├─ postgres (volume pgdata)
                                    ├─ /data/documents (volume documents)
                                    └─ ollama:11434 (volume ollama)
```

PostgreSQL e Ollama **não** têm porta publicada por padrão. Só a porta da UI (`PUBLISH_PORT`, padrão 8080) é exposta.

O backend sobe com **um único worker**. Não escale o serviço `backend`. O descarregamento do modelo é global para quem compartilha o mesmo Ollama e **não** apaga os arquivos instalados.

### Pré-requisitos no servidor

- Docker Engine e Docker Compose v2
- Rede para clonar o GitHub no build e para o primeiro `ollama pull`
- Disco para o modelo Gemma 4 E4B (vários gigabytes) + PDFs + PostgreSQL
- RAM suficiente para carregar `gemma4:e4b` em CPU (confira no hardware; não há garantia de desempenho)
- GPU é **opcional** e depende de drivers no host; a configuração básica é CPU

### Configuração inicial

```bash
git clone -b frontend https://github.com/Guimcv1/Hacktoberfest-Senai-Taguatinga---Gemma.git studybuddy
cd studybuddy
cp .env.example .env
# edite JWT_SECRET (32+ caracteres)
# edite POSTGRES_PASSWORD (evite @ : / na senha)
# CORS_ORIGINS=http://SEU_HOST:8080  se não for localhost
```

Também é possível clonar `-b backend`; o Compose é o mesmo.

### Build e inicialização

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f frontend
```

O backend aplica `alembic upgrade head` no entrypoint, antes de publicar a API.

### Modelo Gemma 4 E4B (manual)

A API **não** executa `ollama pull`. Depois dos contêineres saudáveis:

```bash
docker compose exec ollama ollama pull gemma4:e4b
docker compose exec ollama ollama list
```

A primeira inferência (e a primeira após unload) pode demorar enquanto o modelo entra na memória.

### Verificar serviços

```bash
curl -sS http://localhost:8080/
curl -sS http://localhost:8080/health
docker compose logs backend
docker compose logs postgres
docker compose logs ollama
```

A UI fala com o backend pela **mesma origem** (`/api` no Nginx).

### Atualizar sem apagar dados

```bash
git pull
docker compose build
docker compose up -d
```

Isso recria **contêineres**, não volumes. **Não** use `docker compose down -v`.

| Ação | O que acontece |
| --- | --- |
| `docker compose stop` / `start` | para/inicia; volumes intactos |
| `docker compose up -d --build` | nova imagem; volumes intactos |
| `ollama pull gemma4:e4b` | baixa/atualiza pesos no volume `ollama` |
| `docker compose down -v` | **apaga** PostgreSQL, PDFs e modelos |

### Volumes

| Volume | Dados |
| --- | --- |
| `pgdata` | usuários, conversas, mensagens, questões, texto extraído |
| `documents` | PDFs originais |
| `ollama` | arquivos do modelo |

Volumes **não** são backup. Recomendação (não executada aqui):

```bash
docker compose exec postgres pg_dump -U studybuddy studybuddy > backup.sql
docker compose cp backend:/data/documents ./backup-documents
```

### Parar

```bash
docker compose stop      # mantém volumes
docker compose down      # remove contêineres e rede; mantém volumes nomeados
```

### Diagnóstico

- Backend não sobe: `docker compose logs backend` — JWT_SECRET, senha do Postgres, migração.
- Postgres unhealthy: senha/usuário do `.env` diferentes dos do volume já criado.
- Ollama unreachable: `AI_BASE_URL` deve ser `http://ollama:11434` na rede do Compose.
- 503 na IA: modelo não puxado, ou primeira carga ainda em andamento.
- Unload 409: há inferência neste processo; aguarde.
- UI sem API: o Nginx precisa resolver o serviço `backend`; o navegador não deve chamar `http://backend`.

### CPU / GPU

A configuração publicada não exige GPU. Aceleração NVIDIA exigiria Compose extra e NVIDIA Container Toolkit no host — isso **não** foi validado aqui.

A stack Docker foi **preparada, não executada** neste ambiente.
>>>>>>> e10bbaba10e3d0af0f7636072277845496b3bb03
