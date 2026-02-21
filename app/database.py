from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import TypeVar, Type, Optional, List, Any
from urllib.parse import urlparse, unquote
from app.config import settings


def _build_engine():
    """
    Parse DATABASE_URL and build the engine via URL.create() instead of passing
    a raw string. This ensures the Supabase pooler username (postgres.projectref)
    is passed to psycopg2 as an explicit keyword arg, not via URL string parsing
    which truncates the username at the dot.
    """
    p = urlparse(settings.database_url)
    query = {}
    if p.query:
        for part in p.query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                query[k] = unquote(v)

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=unquote(p.username or ""),       # postgres.stdzdbtdycsszdgvkwmw
        password=unquote(p.password or ""),
        host=p.hostname,
        port=p.port or 5432,
        database=(p.path or "").lstrip("/") or "postgres",
        query=query,
    )
    return create_engine(url, pool_size=10, max_overflow=20, pool_pre_ping=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# ── FastAPI dependency — injected into every route via Depends(get_db) ───────
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Generic CRUD helpers — pass any SQLAlchemy model class into these ─────────
# These are intentionally model-agnostic so you don't repeat boilerplate in every service.

T = TypeVar("T")


def get_by_id(db: Session, model: Type[T], record_id: int) -> Optional[T]:
    """Fetch one row by primary key. Returns None if not found."""
    return db.query(model).filter(model.id == record_id).first()


def get_all(db: Session, model: Type[T], **filters) -> List[T]:
    """
    Fetch all rows matching keyword filter args.
    Example: get_all(db, Hotel, owner_id=5, active=True)
    Each kwarg must match a column name on the model exactly.
    """
    q = db.query(model)
    for attr, value in filters.items():
        q = q.filter(getattr(model, attr) == value)
    return q.all()


def create_record(db: Session, model: Type[T], **kwargs) -> T:
    """
    Insert a single row and return the committed, refreshed ORM instance.
    Example: create_record(db, User, email="a@b.com", password_hash="...")
    """
    instance = model(**kwargs)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def update_record(db: Session, instance: T, **kwargs) -> T:
    """
    Update fields on an already-fetched ORM instance.
    Skips None values so partial PATCH requests work correctly.
    Example: update_record(db, hotel, name="New Name", city="NYC")
    """
    for key, value in kwargs.items():
        if value is not None:
            setattr(instance, key, value)
    db.commit()
    db.refresh(instance)
    return instance


def delete_record(db: Session, instance: T) -> None:
    """Delete an ORM instance and commit immediately."""
    db.delete(instance)
    db.commit()


def bulk_create(db: Session, instances: List[Any]) -> None:
    """
    Bulk insert a list of ORM instances in a single commit.
    Use this for inventory init (365 rows) — never loop with individual commits.
    Example: bulk_create(db, [Inventory(...) for i in range(365)])
    """
    db.bulk_save_objects(instances)
    db.commit()
