"""
Simple retrieval-augmented answering over your local knowledge base.
Always shows the raw retrieved chunks (so you can trust what backs the
answer); if ANTHROPIC_API_KEY is set, also asks Claude to synthesize a
direct answer strictly from those chunks, with source citations.
"""
import json
import urllib.request

import kb
from config import ANTHROPIC_API_KEY


def ask(question, limit=5):
    """CLI entrypoint — prints to stdout."""
    text, results = ask_text(question, limit=limit)
    print(f"\n=== Retrieved {len(results)} chunk(s) from your knowledge base ===")
    kb.print_search_results(results)
    print(f"\n{text}")


def ask_text(question, limit=5):
    """
    Returns (message_text, results) — used by both the CLI and the Telegram
    bot so the retrieval/synthesis logic lives in exactly one place.
    """
    conn = kb.get_conn()
    results = kb.search(conn, question, limit=limit)

    if not results:
        return "No matches in your knowledge base yet. Ingest some material first.", results

    if not ANTHROPIC_API_KEY:
        return "(Set ANTHROPIC_API_KEY to also get a synthesized answer here.)", results

    context = "\n\n".join(
        f"[Source: {r['title']} ({r['source']})]\n{r['chunk']}" for r in results
    )
    prompt = (
        "Answer the question below using ONLY the provided source excerpts. "
        "If the excerpts don't contain enough to answer, say so plainly — "
        "don't fill in gaps from general knowledge. Cite sources by title "
        "inline like (Source: <title>).\n\n"
        f"SOURCES:\n{context}\n\nQUESTION: {question}"
    )
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return ("\n".join(text_blocks) if text_blocks else "(empty response)"), results
    except Exception as e:
        return f"Synthesis request failed: {e}", results
