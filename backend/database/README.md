# PostgreSQL schema

`tafhim_schema.sql` contains Tafhim's PostgreSQL 15+ schema. It is installed by
the Django migration `accounts.0005_tafhim_schema`; the existing account and
case migrations remain in place for the current API.

Configure the PostgreSQL connection in `backend/.env` using `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`. From the `backend`
directory, apply the schema and the rest of the Django migrations with:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

The schema SQL is a fresh-install migration and runs only once through Django's
migration history. It requires permission to create the `pgcrypto` extension.
Original documents and full OCR/source text are intentionally not stored in
this database; use private document storage as described in the SQL comments.

Paperless-ngx is exposed on host port `8002` to avoid colliding with the
Django development server. Keep `PAPERLESS_URL=http://127.0.0.1:8002` and
`PAPERLESS_TOKEN` (or `PAPERLESS_API_TOKEN`) set in `backend/.env`. After
changing the Paperless port, restart the service with:

```powershell
docker compose -f paperless\docker-compose.yml up -d webserver
```
