# Hacktoberfest-Senai-Taguatinga---Gemma

# Equipe :

- Humberto Gabriel Bezerra de Oliveira - humbertobezerradeoliveira@gmail.com
- Guilherme Martins Coelho Vilmar - guimcvilmar@gmail.com
- Arthur Nunes de Carvalho - arthurnunescarvalho2@gmail.com

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
