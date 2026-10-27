# StudyBuddy AI — Hacktoberfest Senai Taguatinga

Plataforma inteligente de estudos onde estudantes interagem com um professor virtual potencializado pelo modelo **Gemma 4 E4B (`gemma4:e4b`)** via **Ollama**. Suporta cadastro e autenticação de usuários, metas de estudos, upload de materiais em PDF com extração de texto e recuperação contextual, e chat interativo com comandos de voz e sintetizador de fala.

## Equipe

- **Arthur Nunes de Carvalho** — arthurnunescarvalho2@gmail.com
- **Guilherme Martins Coelho Vilmar** — guimcvilmar@gmail.com
- **Humberto Gabriel Bezerra de Oliveira** — humbertobezerradeoliveira@gmail.com

---

## Arquitetura do Projeto

```text
Host / Navegador
      │
      ▼  (Porta 8080)
┌────────────────────────────────────────────────────────┐
│ Nginx (Frontend Container)                             │
│ ├─ Serve aplicação React SPA (Vite build)              │
│ └─ Proxy reverso /api/  ───────────────────────┐       │
└────────────────────────────────────────────────┼───────┘
                                                 │
                               Rede Docker       ▼
┌────────────────────────────────────────────────────────┐
│ FastAPI (Backend Container :8000)                      │
│ ├─ Autenticação JWT & CORS                             │
│ ├─ Extração de texto de PDFs (PyMuPDF)                 │
│ ├─ Histórico de conversas e perguntas                  │
│ ├─ PostgreSQL (Container :5432)                        │
│ └─ Ollama / Gemma 4 E4B (Container :11434)             │
└────────────────────────────────────────────────────────┘
```

- **Isolamento de Segurança**: Apenas a porta do frontend (`8080`) é exposta para o host. O PostgreSQL, o Ollama e a API FastAPI comunicam-se exclusivamente pela rede interna do Docker (`app-network`).
- **Nginx como Proxy Reverso**: Todas as requisições `/api/` feitas pelo frontend são encaminhadas internamente pelo Nginx para o backend, eliminando problemas de CORS e URLs hardcoded no navegador.

---

## Executar com Docker Compose (Recomendado)

### 1. Pré-requisitos

- Docker Engine e Docker Compose instalados e em execução.

### 2. Configurar o ambiente

Copie o arquivo de exemplo `.env.example` para `.env` na raiz do projeto:

```bash
cp .env.example .env
```

*(No Windows PowerShell: `Copy-Item .env.example .env`)*

Abra o `.env` e defina as variáveis obrigatórias:

- `JWT_SECRET`: segredo aleatório com pelo menos 32 caracteres (ex.: gerado com `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- `POSTGRES_PASSWORD`: senha segura para o banco PostgreSQL.

### 3. Baixar o modelo no Ollama

Antes ou após iniciar os serviços, faça o download do modelo Gemma 4 E4B no volume do Ollama:

```bash
docker compose run --rm ollama ollama pull gemma4:e4b
```

### 4. Subir a aplicação

Construa as imagens e inicie todos os contêineres:

```bash
docker compose up -d --build
```

### 5. Acessar a aplicação

Acesse no seu navegador:

[http://localhost:8080](http://localhost:8080)

---

## Comandos Úteis

| Ação | Comando |
| :--- | :--- |
| **Ver logs em tempo real** | `docker compose logs -f` |
| **Ver logs específicos** | `docker compose logs -f backend frontend` |
| **Ver status dos contêineres** | `docker compose ps` |
| **Parar os serviços** | `docker compose stop` |
| **Derrubar serviços e rede** | `docker compose down` |
| **Derrubar e apagar volumes** *(Atenção: apaga banco e modelos)* | `docker compose down -v` |
| **Verificar saúde da API** | Acesse `http://localhost:8080/health` |

---

## Desenvolvimento Local (Sem Docker)

### Backend (Python FastAPI)

1. Acesse o diretório `backend`:

   ```bash
   cd backend
   ```

2. Crie e ative um ambiente virtual:

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Inicie o servidor:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend (React + Vite)

1. Acesse o diretório `frontend`:

   ```bash
   cd frontend
   ```

2. Instale as dependências:

   ```bash
   npm install
   ```

3. Inicie o servidor Vite:

   ```bash
   npm run dev
   ```

   *(O Vite já está configurado para repassar `/api` para `http://127.0.0.1:8000` em desenvolvimento).*

---

## Licença

Este projeto está licenciado sob a licença [MIT](LICENSE).
