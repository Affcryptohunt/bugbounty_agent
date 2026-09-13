"""
Tutor mode: curated lessons on bug bounty methodology and common vuln classes.
This is knowledge/methodology, not exploit code — the goal is to teach you how
to think about a target so you can test it manually and responsibly.
"""

LESSONS = {
    "rules": """
LESSON: Rules of the Road
----------------------------------
1. Only test what is explicitly in-scope. Read the program's policy on
   HackerOne/Bugcrowd/Intigriti/YesWeHack before touching anything.
2. Respect rate limits and "no automated scanning" clauses — some programs
   forbid tools like nuclei/nmap entirely. Always check.
3. Never access, exfiltrate, or modify real user data, even if you find a
   path to it. Prove impact with minimal data (e.g. your own test account).
4. No DoS testing unless explicitly allowed.
5. Report privately to the program first (responsible disclosure) — never
   post live vulns publicly before the program says you can.
6. If in doubt, ask the program via their contact channel before proceeding.
""",
    "recon": """
LESSON: Recon Methodology
----------------------------------
Goal: build a map of the attack surface before you touch anything.
1. Scope confirmation — get the exact domains/IPs/apps that are in-scope.
2. Subdomain enumeration (subfinder, amass, crt.sh) -> list of hosts.
3. Host probing (httpx) -> which hosts are alive, what tech (Wappalyzer-style
   fingerprinting), status codes, titles.
4. Content discovery — check for exposed docs, .git, .env, API specs
   (swagger.json), admin panels, staging subdomains.
5. Parameter & endpoint discovery — JS files often reveal API routes and
   hidden parameters (grep for fetch/axios/XHR calls).
6. Tech-stack specific known-CVE checks (nuclei templates) — but only if the
   program allows automated scanning.
Output of this phase: a prioritized list of hosts/endpoints worth manual
testing, not a vulnerability yet.
""",
    "vuln_classes": """
LESSON: Common Vulnerability Classes (conceptual overview)
----------------------------------
- IDOR (Insecure Direct Object Reference): an ID in a URL/API request maps
  directly to a resource with no ownership check. Test by swapping IDs
  between two of your own accounts and see if you can read/edit the other.
- Broken Auth / Session issues: predictable tokens, missing invalidation on
  logout, JWT signature not verified, password reset token reuse.
- XSS (reflected/stored/DOM): untrusted input rendered without encoding.
  Look for input reflected in HTML, JS context, or attributes.
- SSRF: server-side requests built from user input (webhooks, URL
  previews, PDF generators, image fetchers) that can be redirected to
  internal services (metadata endpoints, internal admin panels).
- Business logic flaws: race conditions in payments/coupons, price
  manipulation, workflow bypass (skipping a required step via direct API
  calls).
- Misconfigurations: exposed .git/.env, open S3 buckets, verbose error
  pages leaking stack traces, default creds on admin panels.
This is a map for where to focus manual testing — actual payload crafting
should be done by you, interactively, against an authorized target, ideally
in something like Burp Suite where you can see and control every request.
""",
    "reporting": """
LESSON: Writing a Report That Gets Paid
----------------------------------
Structure that triagers like:
1. Title — short, specific ("IDOR in /api/orders/{id} allows reading other
   users' orders").
2. Summary — 2-3 sentences: what's broken and why it matters.
3. Steps to reproduce — numbered, exact requests (or a short video/gif),
   using your OWN test accounts.
4. Impact — what a real attacker could do, tied to CIA (confidentiality/
   integrity/availability) or business impact.
5. Suggested fix — even a one-liner ("check resource ownership server-side
   before returning it") boosts credibility.
6. CVSS/severity estimate if the program wants one.
Vague reports ("I found a vulnerability") get closed as not-applicable.
Specific, reproducible reports get triaged fast.
""",
    "tools": """
LESSON: The Legit Toolchain
----------------------------------
- Recon: subfinder, amass, assetfinder, httpx, dnsx
- Fuzzing/content discovery: ffuf, gobuster
- Manual testing/proxy: Burp Suite (Community is fine to start), Caido
- Known-CVE scanning: nuclei (only where program permits automated scans)
- JS analysis: LinkFinder, SecretFinder
- Mobile: MobSF (for mobile bug bounty targets)
All of these are legitimate, widely-used, open-source or freemium tools in
the professional bug bounty community — nothing exotic needed to start.
"""
}

ORDER = ["rules", "recon", "vuln_classes", "reporting", "tools"]


def list_topics():
    print("Available lessons:")
    for i, key in enumerate(ORDER, 1):
        print(f"  {i}. {key}")


def show_lesson(key):
    text = LESSONS.get(key)
    if not text:
        print(f"No lesson called '{key}'. Run with no args to see the list.")
        return
    print(text)


def run_all():
    for key in ORDER:
        show_lesson(key)
        input("\n[press Enter for next lesson]\n")
