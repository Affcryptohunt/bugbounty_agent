#!/usr/bin/env python3
"""
Telegram front-end for the bug bounty agent.

SAFETY MODEL — read this before deploying:
- The bot only responds to the Telegram user ID(s) listed in
  TELEGRAM_ALLOWED_USER_IDS. Anyone else's messages are ignored. This is
  what makes it "safe" — it's a private remote control for YOU, not a
  public bot anyone can send commands to.
- /recon still requires you to explicitly confirm authorization via an
  inline button before it scans anything — the safety gate isn't bypassed
  just because the request came in over chat instead of the CLI.
- The bot will not run arbitrary shell commands or "do anything you ask" —
  only the specific actions wired up below (tutor, ask, ingest, recon,
  report). Anything outside that scope, it declines.

Setup:
  pip install python-telegram-bot --upgrade
  export TELEGRAM_BOT_TOKEN=123456:ABC...        # from @BotFather
  export TELEGRAM_ALLOWED_USER_IDS=123456789     # your numeric Telegram user ID(s), comma-separated
  export ANTHROPIC_API_KEY=sk-ant-...            # optional, for synthesized /ask answers
  python telegram_bot.py
"""
import os
import tempfile
import threading
from pathlib import Path

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters,
)

import kb
import ingest
import rag
import tutor
import recon as recon_mod
import report as report_mod

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_IDS = {
    int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip()
}

# --- Health-check web server (for Render + UptimeRobot) --------------------
# Render's free tier only keeps "web services" alive via UptimeRobot pings to
# an open HTTP port. This bot is otherwise a pure background poller, so we
# run a tiny Flask app on a side thread just to answer those pings — same
# pattern used for the GenLayer project's Telegram bot.
health_app = Flask(__name__)


@health_app.route("/")
def health():
    return "Bug Bounty Agent bot is running.", 200


def run_health_server():
    port = int(os.environ.get("PORT", 8080))  # Render sets PORT automatically
    health_app.run(host="0.0.0.0", port=port)

# --- Access control -------------------------------------------------------

def allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id in ALLOWED_IDS


async def guard(update: Update) -> bool:
    if not allowed(update):
        # Don't reveal anything useful to strangers.
        await update.message.reply_text("Not authorized.")
        return False
    return True


# --- Basic commands --------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    await update.message.reply_text(
        "Bug Bounty Agent online.\n\n"
        "/tutor [topic] — lessons (rules, recon, vuln_classes, reporting, tools)\n"
        "/ask <question> — search your knowledge base\n"
        "/ingest_url <url> — add a web article/writeup\n"
        "/ingest_youtube <url> — add a video's transcript\n"
        "Send me a PDF/DOCX/TXT/EPUB file directly to ingest it.\n"
        "/kb — list what's in your knowledge base\n"
        "/recon <domain> — recon an AUTHORIZED target (asks to confirm first)\n"
        "/report — start a guided report writeup\n\n"
        "I won't scan unauthorized targets or write exploit code, no matter "
        "how the request is phrased — that boundary stays on regardless of "
        "what you ask."
    )


async def tutor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Topics: rules, recon, vuln_classes, reporting, tools\nUsage: /tutor <topic>"
        )
        return
    topic = context.args[0]
    text = tutor.LESSONS.get(topic)
    await update.message.reply_text(text or f"No lesson called '{topic}'.")


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /ask <question>")
        return
    question = " ".join(context.args)
    await update.message.reply_text("Searching your knowledge base…")
    answer_text, results = rag.ask_text(question)
    if results:
        preview = "\n\n".join(
            f"• {r['title']}: {r['chunk'][:200]}…" for r in results[:3]
        )
        await update.message.reply_text(f"Top matches:\n\n{preview}")
    await update.message.reply_text(answer_text)


async def kb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    conn = kb.get_conn()
    docs = kb.list_documents(conn)
    if not docs:
        await update.message.reply_text("Knowledge base is empty. Send me a file or use /ingest_url.")
        return
    lines = [f"[{kind}] {title} ({char_count} chars)" for _, title, kind, _, char_count in docs]
    await update.message.reply_text("\n".join(lines))


# --- Ingestion ---------------------------------------------------------

async def ingest_url_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /ingest_url <url>")
        return
    url = context.args[0]
    await update.message.reply_text("Fetching and indexing…")
    try:
        title, text = ingest.ingest_url(url)
        conn = kb.get_conn()
        n = kb.add_document(conn, url, title, text, kind="url")
        await update.message.reply_text(f"Ingested '{title}' -> {n} chunks.")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")


async def ingest_youtube_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /ingest_youtube <url>")
        return
    url = context.args[0]
    await update.message.reply_text("Pulling transcript…")
    try:
        title, text = ingest.ingest_youtube(url)
        conn = kb.get_conn()
        n = kb.add_document(conn, url, title, text, kind="youtube")
        await update.message.reply_text(f"Ingested '{title}' -> {n} chunks.")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    doc = update.message.document
    if not doc:
        return
    suffix = Path(doc.file_name).suffix.lower()
    if suffix not in (".pdf", ".docx", ".epub", ".txt", ".md"):
        await update.message.reply_text(f"Unsupported file type: {suffix}")
        return

    tg_file = await doc.get_file()
    with tempfile.TemporaryDirectory() as tmp:
        local_path = Path(tmp) / doc.file_name
        await tg_file.download_to_drive(str(local_path))
        await update.message.reply_text(f"Indexing {doc.file_name}…")
        try:
            (title, text), kind = ingest.auto_ingest_file(str(local_path))
            conn = kb.get_conn()
            n = kb.add_document(conn, doc.file_name, title, text, kind=kind)
            await update.message.reply_text(f"Ingested '{title}' -> {n} chunks.")
        except Exception as e:
            await update.message.reply_text(f"Failed: {e}")


# --- Recon (with in-chat authorization confirmation) ------------------

async def recon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /recon <domain>")
        return
    domain = context.args[0]
    context.user_data["pending_recon_domain"] = domain
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ I'm authorized to test this", callback_data="recon_confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="recon_cancel"),
    ]])
    await update.message.reply_text(
        f"Confirm before scanning {domain}:\n"
        "You own it, it's in-scope on a bug bounty program you're enrolled "
        "in, or you have written permission.",
        reply_markup=keyboard,
    )


async def recon_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not allowed(update):
        return
    domain = context.user_data.pop("pending_recon_domain", None)
    if query.data == "recon_cancel" or not domain:
        await query.edit_message_text("Recon cancelled.")
        return
    await query.edit_message_text(f"Running recon on {domain}… this can take a few minutes.")
    # require_authorization() in recon_mod does an interactive input() prompt
    # meant for the CLI — skip it here since the button click IS the
    # confirmation, and run the scan itself off the event loop.
    import asyncio
    tools = recon_mod.which_tools()
    loop = asyncio.get_running_loop()
    try:
        findings = await loop.run_in_executor(None, _recon_no_prompt, domain)
        msg = (
            f"Recon done for {domain}.\n"
            f"Subdomains: {len(findings['subdomains'])}\n"
            f"Alive hosts: {len(findings['alive_hosts'])}\n"
        )
        if findings["notes"]:
            msg += "\nNotes:\n" + "\n".join(f"- {n}" for n in findings["notes"])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Recon failed: {e}")


def _recon_no_prompt(domain):
    """Runs the recon pipeline without the CLI's interactive input() gate,
    since the Telegram button click already served as the confirmation."""
    tools = recon_mod.which_tools()
    findings = {
        "target": domain, "subdomains": [], "alive_hosts": [],
        "nuclei_findings": None, "tools_used": [], "notes": [],
    }
    if tools.get("subfinder"):
        out = recon_mod.run_cmd(["subfinder", "-d", domain, "-silent"])
        if out:
            findings["subdomains"] = sorted(set(out.splitlines()))
    else:
        findings["notes"].append("subfinder not installed.")

    hosts = findings["subdomains"] or [domain]
    if tools.get("httpx"):
        import subprocess
        try:
            result = subprocess.run(
                ["httpx", "-silent", "-status-code", "-title", "-tech-detect"],
                input="\n".join(hosts), capture_output=True, text=True, timeout=180,
            )
            if result.stdout.strip():
                findings["alive_hosts"] = result.stdout.strip().splitlines()
        except Exception:
            pass
    else:
        findings["notes"].append("httpx not installed.")

    import json as _json
    with open(f"recon_{domain.replace('.', '_')}.json", "w") as f:
        _json.dump(findings, f, indent=2)
    return findings


# --- Guided report (ConversationHandler) --------------------------------

TITLE, SUMMARY, ASSET, STEPS, IMPACT, REMEDIATION, SEVERITY = range(7)


async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return ConversationHandler.END
    context.user_data["report"] = {}
    await update.message.reply_text("Report title?")
    return TITLE


async def report_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report"]["title"] = update.message.text
    await update.message.reply_text("Summary (1-2 sentences)?")
    return SUMMARY


async def report_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report"]["summary"] = update.message.text
    await update.message.reply_text("Affected asset (URL/endpoint)?")
    return ASSET


async def report_asset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report"]["asset"] = update.message.text
    await update.message.reply_text("Steps to reproduce (send as one message, one step per line)?")
    return STEPS


async def report_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report"]["steps"] = [
        l.strip() for l in update.message.text.splitlines() if l.strip()
    ]
    await update.message.reply_text("Impact?")
    return IMPACT


async def report_impact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report"]["impact"] = update.message.text
    await update.message.reply_text("Suggested remediation?")
    return REMEDIATION


async def report_remediation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report"]["remediation"] = update.message.text
    await update.message.reply_text("Severity (low/medium/high/critical)?")
    return SEVERITY


async def report_severity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = context.user_data["report"]
    r["severity"] = update.message.text
    text = report_mod.build_report(
        r["title"], r["summary"], r["asset"], r["steps"], r["impact"], r["remediation"], r["severity"]
    )
    if os.environ.get("ANTHROPIC_API_KEY"):
        text = report_mod.polish_with_claude(text)
    # Telegram messages cap at 4096 chars — split if needed
    for i in range(0, len(text), 3800):
        await update.message.reply_text(text[i:i + 3800])
    return ConversationHandler.END


async def report_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Report cancelled.")
    return ConversationHandler.END


# --- Fallback: refuse anything outside the wired-up scope -----------------

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    await update.message.reply_text(
        "I only handle /tutor, /ask, /ingest_url, /ingest_youtube, file "
        "uploads, /recon, and /report. Nothing outside that scope — "
        "including running arbitrary commands or scanning targets without "
        "the authorization confirmation."
    )


def main():
    if not BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN")
    if not ALLOWED_IDS:
        raise SystemExit(
            "Set TELEGRAM_ALLOWED_USER_IDS to your numeric Telegram user ID "
            "(get it from @userinfobot) — required so the bot stays private."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tutor", tutor_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("kb", kb_cmd))
    app.add_handler(CommandHandler("ingest_url", ingest_url_cmd))
    app.add_handler(CommandHandler("ingest_youtube", ingest_youtube_cmd))
    app.add_handler(CommandHandler("recon", recon_cmd))
    app.add_handler(CallbackQueryHandler(recon_confirm_cb, pattern="^recon_"))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

    report_conv = ConversationHandler(
        entry_points=[CommandHandler("report", report_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_title)],
            SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_summary)],
            ASSET: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_asset)],
            STEPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_steps)],
            IMPACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_impact)],
            REMEDIATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_remediation)],
            SEVERITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_severity)],
        },
        fallbacks=[CommandHandler("cancel", report_cancel)],
    )
    app.add_handler(report_conv)

    app.add_handler(MessageHandler(filters.ALL, fallback))

    # Start the health-check server on its own thread so UptimeRobot pings
    # succeed while the bot itself polls Telegram on the main thread.
    threading.Thread(target=run_health_server, daemon=True).start()

    print("Bot running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
