"""Connexion à MySQL avec SQLAlchemy 2."""
import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

log = logging.getLogger("todoist.db")

# pool_pre_ping : vérifie la connexion avant usage (utile après un restart de la base)
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def wait_for_db() -> None:
    """Réessaie la connexion tant que MySQL n'est pas prêt."""
    for attempt in range(1, config.DB_CONNECT_RETRIES + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("Base de données joignable (%s:%s)", config.DB_HOST, config.DB_PORT)
            return
        except OperationalError as exc:
            log.warning("Base indisponible (tentative %d/%d) : %s",
                        attempt, config.DB_CONNECT_RETRIES, exc.orig)
            time.sleep(config.DB_CONNECT_DELAY_S)
    raise RuntimeError("Impossible de joindre la base de données")


def get_session():
    """Dépendance FastAPI : une session par requête, fermée à la fin."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
