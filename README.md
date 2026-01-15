# UML Generator Prototype

Prototyp zur Generierung von UML-Aufgaben über eine Weboberfläche und ein Flask-Backend mit PostgreSQL-Speicher.

## Architektur
- **Frontend**: Vue 3 + Vite; stellt Formular zur Parametrisierung bereit.
- **Backend**: Flask REST API verarbeitet Parameter, baut Prompts und ruft ein LLM an.
- **LLM**: Mock-Service (Echo) als Platzhalter für echtes Modell.
- **Datenbank**: PostgreSQL speichert Parameter, Prompts und Ergebnisse.
- **Container-Orchestrierung**: docker-compose.

## Entwicklungs-Setup
```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

## Tests (Backend)
```bash
cd backend
pytest
```

## Start über Docker
```bash
docker compose up --build
```

Frontend läuft anschließend auf `http://localhost:5173`, Backend auf `http://localhost:5000`.

