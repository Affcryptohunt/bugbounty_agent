# Bug Bounty Agent

A CLI toolkit for **authorized** whitehat security testing / bug bounty work.
Three modes:

1. **Tutor** — curated lessons on methodology, vuln classes, and reporting.
2. **Recon** — orchestrates open-source recon tools (subfinder, httpx,
   optionally nuclei) against a target you confirm you're authorized to test.
3. **Report** — turns your findings into a clean, submission-ready markdown
   report, optionally polished for wording via the Claude API.

## What this is NOT
This does not contain exploit code, payload generators, or "auto-hack"
logic. It automates recon you'd otherwise run manually and helps you write
up what *you* found. Actual vulnerability testing (crafting payloads,
manipulating requests) should be done interactively by you — a proxy tool
like **Burp Suite Community Edition** is the standard way to do that, since
it lets you see and control every request.

## Setup

```bash
cd bugbounty_agent
python3 -m venv venv
source venv/bin/activate   # Windows: venv\\Scripts\\activate
pip install -r requirements.txt   # no hard deps, but keeps the venv clean
```

Recon features are optional add-ons — install what you want to use:

```bash
# Go is required for these (https://go.dev/doc/install)
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest   # optional
```

If ProjectDiscovery's Go bin dir isn't on your PATH yet:
```bash
export PATH=$PATH:$(go env GOPATH)/bin
```

For report polishing, set your own Anthropic API key (optional):
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# Learn
python cli.py tutor                # list lessons
python cli.py tutor rules          # read one lesson
python cli.py tutor all            # walk through everything

# Recon (asks you to confirm authorization first)
python cli.py recon example.com
python cli.py recon example.com --allow-nuclei   # only if program allows automated scans

# Build a report from findings you write in
python cli.py report

# --- Knowledge base: teach it from books, courses, videos, docs ---
python cli.py ingest --file "web-hacking-101.pdf" --tags "book xss"
python cli.py ingest --file notes.docx
python cli.py ingest --file some_ebook.epub
python cli.py ingest --youtube "https://youtube.com/watch?v=XXXXXXXX"   # pulls the video's transcript/captions
python cli.py ingest --url "https://some-writeup.com/cool-idor-bug"

python cli.py kb-list                       # see everything you've ingested
python cli.py ask "how do I test for SSRF"  # searches your knowledge base
```

`ask` always shows you the raw retrieved excerpts from your own material. If
you've set `ANTHROPIC_API_KEY`, it also asks Claude to synthesize a direct
answer, strictly grounded in those excerpts and cited by source — so the
tutor's answers scale with whatever books/courses/videos you feed it,
instead of being limited to the five built-in lessons.

Everything ingested lives in a local `knowledge.db` file (SQLite) next to
the CLI — nothing is uploaded anywhere except the excerpts sent to the
Claude API at query time, only if you've opted into that by setting the key.

**Note on YouTube ingestion:** this pulls the transcript/captions already
published on the video (same as clicking "Show transcript"), not the video
file itself — so it only works for videos that have captions available, and
you should stick to your own notes/summary use, not republishing.

### Install ingestion dependencies
Only install what you'll actually use:
```bash
pip install pypdf                    # for .pdf
pip install python-docx              # for .docx
pip install ebooklib beautifulsoup4  # for .epub
pip install requests beautifulsoup4  # for --url
pip install youtube-transcript-api   # for --youtube
```

## Telegram bot (chat interface)

You can control everything above from a private Telegram bot instead of the
terminal — same underlying code, just a chat front-end.

**Safety model**, so it's clear what "safe" means here:
- The bot only responds to your Telegram user ID (or IDs you list). Anyone
  else's messages are silently ignored — it's a remote control for you, not
  a public bot.
- `/recon` still requires an explicit "I'm authorized" button tap before it
  scans anything — moving to chat doesn't remove that gate.
- It only does the specific things wired up (tutor, ask, ingest, recon,
  report). It does not run arbitrary shell commands and will decline
  anything outside that scope, however the request is phrased.

Setup:
```bash
pip install python-telegram-bot flask --upgrade
```
1. Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`,
   copy the token it gives you.
2. Message [@userinfobot](https://t.me/userinfobot) to get your own numeric
   Telegram user ID.
3. Set env vars and run:
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_ALLOWED_USER_IDS="123456789"   # your ID; comma-separate for more than one
export ANTHROPIC_API_KEY="sk-ant-..."          # optional, for synthesized /ask + report polish
python telegram_bot.py
```
Then in Telegram, message your bot: `/start` to see the command list.
Commands: `/tutor <topic>`, `/ask <question>`, send a file directly to
ingest it, `/ingest_url <url>`, `/ingest_youtube <url>`, `/kb`,
`/recon <domain>` (button-confirmed), `/report` (guided, multi-step).

### Free 24/7 hosting: Render + UptimeRobot
This is the same setup already used for the GenLayer project's Telegram
bot — no card needed for either service.

1. Push this project to a GitHub repo (same as the earlier Railway steps —
   github.com > New repository > upload the files).
2. Go to **render.com**, sign up with GitHub, click **New > Web Service**,
   pick your repo.
3. Set the **Start Command** to `python telegram_bot.py`.
4. Under **Environment**, add `TELEGRAM_BOT_TOKEN` and
   `TELEGRAM_ALLOWED_USER_IDS` (and `ANTHROPIC_API_KEY` if you want it) —
   same values as above.
5. Deploy. Render gives you a public URL like
   `https://your-bot-name.onrender.com`.
6. Go to **uptimerobot.com**, sign up (free, no card), add a new monitor
   pointed at that URL, checking every 5 minutes. This keeps Render's free
   tier from putting the service to sleep from inactivity.

The bot includes a tiny built-in health-check endpoint (`/`) just for
UptimeRobot to ping — it doesn't affect the actual Telegram bot logic,
which still runs by polling Telegram in the background exactly as before.

## Getting started as a bug hunter (suggested order)
1. Run `python cli.py tutor all` once, front to back.
2. Sign up on HackerOne / Bugcrowd / Intigriti, pick a program with a public
   scope and decent response history.
3. Install Burp Suite Community Edition, set it as your browser proxy.
4. Run `python cli.py recon <in-scope-domain>` to map the attack surface.
5. Manually test the most interesting hosts/endpoints in Burp, using the
   `tutor vuln_classes` lesson as your checklist.
6. Use `python cli.py report` to write up anything you find.

## Legal note
Only ever point this at assets you own or that are explicitly in-scope on a
bug bounty program you're enrolled in, with the program's current rules of
engagement followed (rate limits, allowed tools, disclosure process).
Unauthorized testing of systems is illegal in most countries even with good
intentions.
