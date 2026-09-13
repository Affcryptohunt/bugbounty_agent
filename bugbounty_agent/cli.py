#!/usr/bin/env python3
"""
Bug Bounty Agent — CLI
A learning + recon-orchestration + report-writing assistant for authorized
whitehat / bug bounty work.

Usage:
    python cli.py tutor                     # list lessons
    python cli.py tutor rules               # show one lesson
    python cli.py tutor all                 # walk through all lessons
    python cli.py recon example.com         # run recon (asks for auth confirmation)
    python cli.py recon example.com --allow-nuclei
    python cli.py report                    # interactive report builder
"""
import argparse
import sys

import tutor
import recon as recon_mod
import report as report_mod
import kb
import ingest
import rag


def cmd_tutor(args):
    if not args.topic:
        tutor.list_topics()
    elif args.topic == "all":
        tutor.run_all()
    else:
        tutor.show_lesson(args.topic)


def cmd_recon(args):
    recon_mod.recon(args.domain, allow_nuclei=args.allow_nuclei, out_path=args.out)


def cmd_report(args):
    print("=== Report Builder ===")
    title = input("Title: ").strip()
    summary = input("Summary: ").strip()
    asset = input("Affected asset (URL/endpoint): ").strip()
    print("Steps to reproduce (one per line, blank line to finish):")
    steps = []
    while True:
        line = input(f"  {len(steps)+1}. ")
        if not line.strip():
            break
        steps.append(line.strip())
    impact = input("Impact: ").strip()
    remediation = input("Suggested remediation: ").strip()
    severity = input("Self-assessed severity (low/medium/high/critical): ").strip()

    raw = report_mod.build_report(title, summary, asset, steps, impact, remediation, severity)

    polish = input("Polish wording via Claude API? (needs ANTHROPIC_API_KEY) [y/N]: ").strip().lower()
    final = report_mod.polish_with_claude(raw) if polish == "y" else raw

    out = args.out or "report.md"
    report_mod.save_report(final, out)


def cmd_ingest(args):
    conn = kb.get_conn()
    if args.file:
        (title, text), kind = ingest.auto_ingest_file(args.file)
        source = args.file
    elif args.youtube:
        title, text = ingest.ingest_youtube(args.youtube)
        source, kind = args.youtube, "youtube"
    elif args.url:
        title, text = ingest.ingest_url(args.url)
        source, kind = args.url, "url"
    else:
        print("Specify one of --file, --youtube, or --url")
        return

    if not text or not text.strip():
        print("No text extracted — nothing to ingest.")
        return

    n = kb.add_document(conn, source, args.title or title, text, kind=kind, tags=args.tags or "")
    print(f"Ingested '{title}' -> {n} chunks indexed (source: {source})")


def cmd_kb_list(args):
    conn = kb.get_conn()
    docs = kb.list_documents(conn)
    if not docs:
        print("Knowledge base is empty. Use 'ingest' to add material.")
        return
    for source, title, kind, added_at, char_count in docs:
        print(f"[{kind}] {title}  ({char_count} chars)  <- {source}")


def cmd_ask(args):
    rag.ask(args.question, limit=args.limit)


def main():
    parser = argparse.ArgumentParser(description="Bug Bounty Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tutor = sub.add_parser("tutor", help="Learn bug bounty methodology")
    p_tutor.add_argument("topic", nargs="?", help="rules|recon|vuln_classes|reporting|tools|all")
    p_tutor.set_defaults(func=cmd_tutor)

    p_recon = sub.add_parser("recon", help="Run recon against an authorized target")
    p_recon.add_argument("domain", help="Target domain, e.g. example.com")
    p_recon.add_argument("--allow-nuclei", action="store_true",
                          help="Enable nuclei scanning (only if program policy allows automated scans)")
    p_recon.add_argument("--out", help="Output JSON path")
    p_recon.set_defaults(func=cmd_recon)

    p_report = sub.add_parser("report", help="Build a submission-ready report")
    p_report.add_argument("--out", help="Output markdown path")
    p_report.set_defaults(func=cmd_report)

    p_ingest = sub.add_parser("ingest", help="Add a book/PDF/doc/YouTube video/article to the knowledge base")
    p_ingest.add_argument("--file", help="Path to a .pdf, .docx, .epub, or .txt/.md file")
    p_ingest.add_argument("--youtube", help="YouTube video URL or ID (pulls its transcript)")
    p_ingest.add_argument("--url", help="Web page URL (article, writeup, docs page)")
    p_ingest.add_argument("--title", help="Override the auto-detected title")
    p_ingest.add_argument("--tags", help="Free-text tags, e.g. 'recon idor'")
    p_ingest.set_defaults(func=cmd_ingest)

    p_kb = sub.add_parser("kb-list", help="List everything in your knowledge base")
    p_kb.set_defaults(func=cmd_kb_list)

    p_ask = sub.add_parser("ask", help="Ask a question against your knowledge base")
    p_ask.add_argument("question")
    p_ask.add_argument("--limit", type=int, default=5, help="How many chunks to retrieve")
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
