# Alembic Migration Reference

## How It Works

Alembic compares your **SQLAlchemy models** (`app/models/`) against the **live database schema** and generates SQL migration scripts.

```
app/models/*.py  →  alembic autogenerate  →  alembic/versions/xxxx_name.py  →  alembic upgrade head  →  Supabase
```

Migration files live in `alembic/versions/`. **Never edit them by hand** unless fixing a bug.

---

## Common Commands

### First-time setup (already done)
```powershell
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

### After modifying any model (add a column, new table, etc.)
```powershell
# 1. Generate migration from model changes
alembic revision --autogenerate -m "describe_what_changed"

# 2. Apply it to the database
alembic upgrade head
```

### Check current state
```powershell
# Show which revision the DB is on
alembic current

# Show full migration history
alembic history --verbose
```

### Rollback one migration
```powershell
alembic downgrade -1
```

### Rollback to a specific revision ID
```powershell
alembic downgrade <revision_id>
# Example: alembic downgrade a3f91c2b
```

### Rollback everything (wipe all tables)
```powershell
alembic downgrade base
```

---

## Workflow for adding a new field

1. Add the column to the SQLAlchemy model in `app/models/<file>.py`
2. Run:
   ```powershell
   alembic revision --autogenerate -m "add_<column>_to_<table>"
   alembic upgrade head
   ```
3. Verify in **Supabase → Table Editor** that the column appears

---

## Workflow for adding a new table

1. Create the model file in `app/models/`
2. Add it to `app/models/__init__.py` exports
3. Run:
   ```powershell
   alembic revision --autogenerate -m "add_<tablename>_table"
   alembic upgrade head
   ```

---

## Connection

Migrations use the `DATABASE_URL` from `.env` (Session pooler, port 5432).
The engine is built in `app/database.py → _build_engine()`.
Alembic reads it via `alembic/env.py` which imports the engine directly.

```
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

> **Note:** Always activate the venv first: `.\venv\Scripts\Activate.ps1`

---

## Gotchas

| Problem | Fix |
|---|---|
| `Target database is not up to date` | Run `alembic upgrade head` first |
| Migration detects no changes | Make sure the model is imported in `app/models/__init__.py` |
| `Can't locate revision` | A version file was deleted — check `alembic/versions/` |
| Column renamed = detected as drop+add | Alembic can't detect renames — add `op.alter_column()` manually in the migration file |
| `alembic.ini` `%` error | Don't put `%` in DATABASE_URL in the ini file — use `.env` only |
