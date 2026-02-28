# UML Generator Prototype

This project generates UML class diagram exercises via a web UI (Vue) and a Flask backend with a PostgreSQL database.

The easiest way to run everything is with Docker and Docker Compose.

---

## Architecture overview

- `frontend/`
  - `src/App.vue` – main Vue component with the parameter form and result view
  - `src/main.js` – Vue app entry point
  - `Dockerfile` – container for the frontend dev server
- `backend/`
  - `app.py` – Flask API (main entry point)
  - `models.py` – SQLAlchemy models for requests and evaluation results
  - `services/llm_client.py` – LLM client and prompt construction
  - `requirements.txt` – Python dependencies
  - `Dockerfile` – container for the backend service
- `database/`
  - `*.sql` – PostgreSQL dumps with existing data (can be imported into the `db` container)
- `docker-compose.yml` – starts `backend`, `frontend` and `db` together

---

## 1. Quick start with Docker (recommended)

### 1.1 Requirements

- Docker
- Docker Compose

### 1.2 One-time setup

1. Clone this repository.
2. Go to the backend folder and create a local environment file:

   ```bash
   cd backend
   cp .env .env.local
   ```

3. Open `backend/.env.local` in an editor and fill in your real API keys/URLs:

   ```env
   OPENAI_API_KEY="sk-..."      # if you want to use OpenAI
   BISAI_BASE_URL="https://..." # if you have a BaSiAI/OpenAI-compatible endpoint
   BISAI_API_KEY="sk-..."       # key for BaSiAI endpoint
   GEMINI_API_KEY="..."         # if you want to use Google Gemini
   ```

   You can leave entries empty if you do not use a particular provider, but the backend must have at least one working model configuration.

4. Go back to the project root (where `docker-compose.yml` is located):

   ```bash
   cd ..
   ```

### 1.3 Start all services

From the project root:

```bash
docker compose up --build
```

This builds and starts:

- `backend`: Flask API on port `5000`
- `frontend`: Vue app on port `5173`
- `db`: PostgreSQL database on port `55432` (host) / `5432` (container)

When the containers are up:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:5000>

To stop everything:

```bash
docker compose down
```

If you change backend or frontend code and want to rebuild:

```bash
docker compose up --build backend frontend
```

---

## 2. Environment variables used by the backend

The backend reads its configuration as follows:

- Standard environment variables:
  - `OPENAI_API_KEY`
  - `BISAI_BASE_URL`
  - `BISAI_API_KEY`
  - `GEMINI_API_KEY`
- Additionally, the file `backend/.env.local` is loaded automatically (if it exists) and can provide the same variables for local development.

The database URL is set in `docker-compose.yml` for the backend container:

```yaml
environment:
  - DATABASE_URL=postgresql+psycopg2://uml_user:uml_pass@db:5432/uml_tasks
```

You normally do not need to change this.

---

## 3. Database and provided data

### 3.1 Database inside Docker

`docker-compose.yml` starts a PostgreSQL 15 container with:

- User: `uml_user`
- Password: `uml_pass`
- Database: `uml_tasks`

The backend creates its tables (`generation_requests`, `evaluation_results`) on first start.

### 3.2 Existing data dump

The folder `database/` contains a SQL dump with existing data, for example:

- `database/generatedData_localhost-2026_02_28_04_38_02-dump.sql`

You can import this into the Docker PostgreSQL instance if you want to pre-load sample data.

#### Import steps

1. Make sure the `db` service is running:

   ```bash
   docker compose up -d db
   ```

2. Copy the dump file into the `db` container. The exact container name may differ; you can check with `docker ps`. Two common variants are shown below; one of them should work:

   ```bash
   # Variant 1: using a fixed container name (adapt if needed)
   docker cp database/generatedData_localhost-2026_02_28_04_38_02-dump.sql UMLGenerator-Prototyp-db-1:/tmp/dump.sql

   # Variant 2: find the container by name pattern
   docker cp database/generatedData_localhost-2026_02_28_04_38_02-dump.sql \
     $(docker ps --filter "name=umlgenerator-prototyp-db" -q | head -n 1):/tmp/dump.sql
   ```

3. Inside the container, run `psql` to import the dump into `uml_tasks`:

   ```bash
   docker exec -it UMLGenerator-Prototyp-db-1 \
     psql -U uml_user -d uml_tasks -f /tmp/dump.sql
   ```

   Adjust the container name if it is different on your system (`docker ps` shows the correct name).

After the import, the backend will see the restored `generation_requests` and `evaluation_results` when you use the application.

---

## 4. Optional: run without Docker (development only)

You can also run frontend and backend directly on your machine. This is only needed for development; for normal use, Docker is easier.

### 4.1 Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ensure Postgres is running locally and DATABASE_URL is set if you do not use Docker
# Also ensure backend/.env.local contains your API keys
python app.py
```

The backend will listen on `http://0.0.0.0:5000`.

### 4.2 Frontend

```bash
cd frontend
npm install
npm run dev -- --host
```

The frontend will listen on `http://localhost:5173`.


---

## 6. Summary

1. Create `backend/.env.local` from `backend/.env` and insert your LLM API keys.
2. From the project root, run:

   ```bash
   docker compose up --build
   ```

3. Open <http://localhost:5173> in a browser and use the UI.
4. (Optional) Import the SQL dump from `database/` into the `db` container if you need the existing data.
