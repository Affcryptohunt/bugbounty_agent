"""
Webhook version of the bot, built for PythonAnywhere's free web-app hosting
(which doesn't support always-on background workers on the free tier, but
does support a free always-on web app). Telegram pushes updates to this
Flask endpoint instead of the bot polling Telegram for them.

Covers: /tutor, /ask, /kb, /ingest_url, /ingest_youtube, and file uploads
(pdf/docx/epub/txt/md). Recon isn't included here since PythonAnywhere
doesn't have subfinder/httpx installed and can't install arbitrary system
binaries on the free tier — run recon locally with cli.py when you need it,
using this bot for tutoring/knowledge-base/lookups day to day.

Setup: see PYTHONANYWHERE_SETUP.md in this folder.
"""
import os

import pa_config

# Set this before importing modules that read ANTHROPIC_API_KEY at import
# time, so /ask synthesis and /report polishing pick it up.
if pa_config.ANTHROPIC_API_KEY:
    os.environ["ANTHROPIC_API_KEY"] = pa_config.ANTHROPIC_API_KEY

import tempfile
from pathlib import Path

import requests
from flask import Flask, request

import kb
import ingest
import rag
import tutor
import report as report_mod

app = Flask(__name__)
TELEGRAM_API = f"https://api.telegram.org/bot{pa_config.TELEGRAM_BOT_TOKEN}"


def send_message(chat_id, text):
    if not text:
        text = "(empty)"
    for i in range(0, len(text), 3800):
        try:
            requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": text[i:i + 3800]},
                timeout=20,
            )
        except Exception:
            pass


def download_telegram_file(file_id, dest_path):
    r = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=20)
    file_path = r.json()["result"]["file_path"]
    url = f"https://api.telegram.org/file/bot{pa_config.TELEGRAM_BOT_TOKEN}/{file_path}"
    data = requests.get(url, timeout=60).content
    Path(dest_path).write_bytes(data)


@app.route("/")
def index():
    return "Bug Bounty Agent webhook bot is running."


@app.route(f"/webhook/{pa_config.WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = request.get_json(force=True, silent=True) or {}
    message = update.get("message") or update.get("channel_post")
    if not message:
        return "ok"

    user_id = message.get("from", {}).get("id")
    chat_id = message["chat"]["id"]

    if user_id not in pa_config.TELEGRAM_ALLOWED_USER_IDS:
        return "ok"  # silently ignore anyone who isn't you

    try:
        if "document" in message:
            handle_document(chat_id, message["document"])
        else:
            handle_text(chat_id, message.get("text", ""))
    except Exception as e:
        send_message(chat_id, f"Something went wrong: {e}")

    return "ok"


def handle_text(chat_id, text):
    text = (text or "").strip()
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/start", "/help"):
        send_message(chat_id, (
            "Bug Bounty Agent (webhook mode)\n\n"
            "/tutor [topic] - rules, recon, vuln_classes, reporting, tools\n"
            "/ask <question> - search your knowledge base\n"
            "/ingest_url <url> - add a web article/writeup\n"
            "/ingest_youtube <url> - add a video's transcript\n"
            "Send a PDF/DOCX/EPUB/TXT file directly to ingest it.\n"
            "/kb - list what's in your knowledge base\n\n"
            "Recon isn't available here (PythonAnywhere can't run the "
            "scanner binaries) - use cli.py on your own machine for that."
        ))

    elif cmd == "/tutor":
        if not arg:
            send_message(chat_id, "Topics: rules, recon, vuln_classes, reporting, tools")
        else:
            send_message(chat_id, tutor.LESSONS.get(arg, f"No lesson called '{arg}'."))

    elif cmd == "/ask":
        if not arg:
            send_message(chat_id, "Usage: /ask <question>")
            return
        answer, results = rag.ask_text(arg)
        if results:
            preview = "\n\n".join(f"- {r['title']}: {r['chunk'][:200]}…" for r in results[:3])
            send_message(chat_id, f"Top matches:\n\n{preview}")
        send_message(chat_id, answer)

    elif cmd == "/kb":
        conn = kb.get_conn()
        docs = kb.list_documents(conn)
        if not docs:
            send_message(chat_id, "Knowledge base is empty. Send me a file or use /ingest_url.")
        else:
            lines = [f"[{k}] {t} ({c} chars)" for _, t, k, _, c in docs]
            send_message(chat_id, "\n".join(lines))

    elif cmd == "/ingest_url":
        if not arg:
            send_message(chat_id, "Usage: /ingest_url <url>")
            return
        try:
            title, txt = ingest.ingest_url(arg)
            conn = kb.get_conn()
            n = kb.add_document(conn, arg, title, txt, kind="url")
            send_message(chat_id, f"Ingested '{title}' -> {n} chunks.")
        except Exception as e:
            send_message(chat_id, f"Failed: {e}")

    elif cmd == "/ingest_youtube":
        if not arg:
            send_message(chat_id, "Usage: /ingest_youtube <url>")
            return
        try:
            title, txt = ingest.ingest_youtube(arg)
            conn = kb.get_conn()
            n = kb.add_document(conn, arg, title, txt, kind="youtube")
            send_message(chat_id, f"Ingested '{title}' -> {n} chunks.")
        except Exception as e:
            send_message(chat_id, f"Failed: {e}")

    else:
        send_message(chat_id, "Unknown command. Send /start to see what I can do.")


def handle_document(chat_id, doc):
    filename = doc.get("file_name", "file")
    suffix = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".epub", ".txt", ".md"):
        send_message(chat_id, f"Unsupported file type: {suffix}")
        return

    send_message(chat_id, f"Downloading and indexing {filename}…")
    with tempfile.TemporaryDirectory() as tmp:
        local_path = Path(tmp) / filename
        download_telegram_file(doc["file_id"], local_path)
        (title, text), kind = ingest.auto_ingest_file(str(local_path))
        conn = kb.get_conn()
        n = kb.add_document(conn, filename, title, text, kind=kind)
        send_message(chat_id, f"Ingested '{title}' -> {n} chunks.")


if __name__ == "__main__":
    # Local testing only — on PythonAnywhere, the WSGI config points at
    # the `app` object above directly; this block never runs there.
    app.run(debug=True)
