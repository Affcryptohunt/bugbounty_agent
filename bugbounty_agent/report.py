"""
Report generator: turns your own findings (you supply the details — this
does not invent vulnerabilities) into a clean, submission-ready markdown
report. Optionally polishes the wording via the Anthropic API if you've set
ANTHROPIC_API_KEY yourself.
"""
import json
import urllib.request

from config import ANTHROPIC_API_KEY

TEMPLATE = """# {title}

## Summary
{summary}

## Affected Asset
{asset}

## Steps to Reproduce
{steps}

## Impact
{impact}

## Suggested Remediation
{remediation}

## Severity (self-assessed)
{severity}
"""


def build_report(title, summary, asset, steps, impact, remediation, severity):
    steps_fmt = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    return TEMPLATE.format(
        title=title,
        summary=summary,
        asset=asset,
        steps=steps_fmt,
        impact=impact,
        remediation=remediation,
        severity=severity,
    )


def polish_with_claude(raw_report):
    """
    Sends your own draft report to the Claude API to tighten the wording
    (grammar, clarity, professional tone) — it does not add any new claims
    or technical details you didn't already write.
    Requires ANTHROPIC_API_KEY to be set in your environment.
    """
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY not set — skipping polish, returning raw report.")
        return raw_report

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1500,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Rewrite the following bug bounty report for clarity and "
                    "professional tone. Do not add, remove, or guess at any "
                    "technical facts — only improve wording and structure. "
                    "Return only the rewritten markdown.\n\n" + raw_report
                ),
            }
        ],
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
        return "\n".join(text_blocks) if text_blocks else raw_report
    except Exception as e:
        print(f"Polish request failed ({e}); returning raw report.")
        return raw_report


def save_report(text, out_path="report.md"):
    with open(out_path, "w") as f:
        f.write(text)
    print(f"Report written to {out_path}")
