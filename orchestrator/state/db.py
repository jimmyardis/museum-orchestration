import sqlite3
from contextlib import contextmanager
from ..config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS personas (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hall TEXT,
    status TEXT DEFAULT 'pending',
    vector_count INTEGER DEFAULT 0,
    page_url TEXT,
    voice_id TEXT,
    last_updated TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    persona_id TEXT,
    agent_name TEXT NOT NULL,
    status TEXT DEFAULT 'queued',
    started_at TEXT,
    completed_at TEXT,
    error_msg TEXT,
    output_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (persona_id) REFERENCES personas(id)
);

CREATE TABLE IF NOT EXISTS agent_stats (
    agent_name TEXT PRIMARY KEY,
    status TEXT DEFAULT 'idle',
    last_run TEXT,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    current_job_id TEXT
);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    agent_name TEXT,
    persona_id TEXT,
    error_type TEXT,
    error_msg TEXT,
    stack_trace TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Seed agent_stats rows so status queries always return all agents
        agents = [
            "persona_identifier", "corpus_fetcher", "corpus_cleaner",
            "pinecone_uploader", "page_generator", "railway_deployer", "tts_auditioner",
        ]
        for agent in agents:
            conn.execute(
                "INSERT OR IGNORE INTO agent_stats (agent_name) VALUES (?)", (agent,)
            )
