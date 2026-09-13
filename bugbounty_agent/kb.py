"""
Local knowledge base: stores chunks of text you ingest (from books, PDFs,
course notes, YouTube transcripts, articles, etc.) in a SQLite FTS5 index so
the tutor can search and cite them later. Everything lives in one file,
knowledge.db, next to the CLI — fully local, nothing uploaded anywhere.
"""
import sqlite3
import textwrap
from pathlib import Path

DB_PATH = Path(__file__).parent / "knowledge.db"

CHUNK_SIZE = 900       # chars per chunk
CHUNK_OVERLAP = 150    # chars of overlap between consecutive chunks


def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
            source, title, chunk, tags
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            source TEXT PRIMARY KEY,
            title TEXT,
            kind TEXT,
            added_at TEXT,
            char_count INTEGER
        )
    """)
    return conn


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = " ".join(text.split())  # normalize whitespace
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
        if start < 0:
            start = 0
        if end >= len(text):
            break
    return chunks


def add_document(conn, source, title, text, kind="text", tags=""):
    """
    source: unique identifier (file path, URL, or video ID)
    title:  human-readable title
    text:   full extracted text
    kind:   'pdf' | 'docx' | 'txt' | 'youtube' | 'url'
    tags:   free-text tags, e.g. "recon idor" for later filtering
    """
    from datetime import datetime, timezone

    conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
    chunks = chunk_text(text)
    conn.executemany(
        "INSERT INTO chunks (source, title, chunk, tags) VALUES (?, ?, ?, ?)",
        [(source, title, c, tags) for c in chunks],
    )
    conn.execute(
        """INSERT INTO documents (source, title, kind, added_at, char_count)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(source) DO UPDATE SET
             title=excluded.title, kind=excluded.kind,
             added_at=excluded.added_at, char_count=excluded.char_count""",
        (source, title, kind, datetime.now(timezone.utc).isoformat(), len(text)),
    )
    conn.commit()
    return len(chunks)


STOPWORDS = {
    "a", "an", "the", "how", "do", "does", "did", "i", "is", "are", "was",
    "were", "to", "of", "in", "on", "for", "and", "or", "what", "why",
    "can", "should", "would", "with", "my", "me", "you", "it", "this",
    "that",
}


def search(conn, query, limit=5):
    # Quote each term (FTS5 needs it for safety) and OR them, ranked by
    # relevance (bm25) — so a question doesn't need to exactly match every
    # word in a chunk, just the meaningful ones.
    words = [w for w in query.split() if w.lower() not in STOPWORDS] or query.split()
    terms = " OR ".join(f'"{w}"' for w in words)
    rows = conn.execute(
        """SELECT source, title, chunk
           FROM chunks WHERE chunks MATCH ?
           ORDER BY bm25(chunks)
           LIMIT ?""",
        (terms, limit),
    ).fetchall()
    return [{"source": s, "title": t, "chunk": c} for s, t, c in rows]


def list_documents(conn):
    return conn.execute(
        "SELECT source, title, kind, added_at, char_count FROM documents ORDER BY added_at DESC"
    ).fetchall()


def print_search_results(results):
    if not results:
        print("No matches in your knowledge base yet.")
        return
    for r in results:
        print(f"\n--- {r['title']}  ({r['source']}) ---")
        print(textwrap.fill(r["chunk"], width=88))
