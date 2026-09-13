"""
Recon orchestrator: runs OPEN-SOURCE recon tools you already have installed
(subfinder, httpx, nuclei, ...) against a target you've confirmed you're
authorized to test, and aggregates the output into one JSON summary.

This module does not contain any exploit or attack logic. It just shells out
to well-known recon tools and collects their output for you to review.
"""
import json
import subprocess
import shutil
import sys
from datetime import datetime, timezone

from config import which_tools, require_authorization


def run_cmd(cmd, timeout=120):
    try:
        result = subprocess.run(
            cmd, shell=False, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return "[timed out]"


def recon(domain, allow_nuclei=False, out_path=None):
    require_authorization()

    tools = which_tools()
    findings = {
        "target": domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subdomains": [],
        "alive_hosts": [],
        "nuclei_findings": None,
        "tools_used": [],
        "notes": [],
    }

    # 1. Subdomain enumeration
    if tools.get("subfinder"):
        out = run_cmd(["subfinder", "-d", domain, "-silent"])
        if out:
            findings["subdomains"] = sorted(set(out.splitlines()))
            findings["tools_used"].append("subfinder")
    else:
        findings["notes"].append(
            "subfinder not installed — skipping subdomain enumeration. "
            "Install: https://github.com/projectdiscovery/subfinder"
        )

    hosts = findings["subdomains"] or [domain]

    # 2. Host probing
    if tools.get("httpx"):
        proc_input = "\n".join(hosts)
        try:
            result = subprocess.run(
                ["httpx", "-silent", "-status-code", "-title", "-tech-detect"],
                input=proc_input,
                capture_output=True,
                text=True,
                timeout=180,
            )
            out = result.stdout.strip()
            if out:
                findings["alive_hosts"] = out.splitlines()
                findings["tools_used"].append("httpx")
        except FileNotFoundError:
            findings["notes"].append("httpx invocation failed unexpectedly.")
    else:
        findings["notes"].append(
            "httpx not installed — skipping host probing. "
            "Install: https://github.com/projectdiscovery/httpx"
        )

    # 3. Known-CVE / misconfig templates via nuclei — OFF by default.
    # Many programs explicitly forbid automated vuln scanners. Only enable
    # this with --allow-nuclei once you've confirmed the program permits it.
    if allow_nuclei:
        if tools.get("nuclei"):
            target_list = findings["alive_hosts"] or hosts
            proc_input = "\n".join(target_list)
            try:
                result = subprocess.run(
                    ["nuclei", "-silent", "-severity", "low,medium,high,critical"],
                    input=proc_input,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                findings["nuclei_findings"] = result.stdout.strip().splitlines()
                findings["tools_used"].append("nuclei")
            except FileNotFoundError:
                findings["notes"].append("nuclei invocation failed unexpectedly.")
        else:
            findings["notes"].append(
                "nuclei not installed. Install: https://github.com/projectdiscovery/nuclei"
            )
    else:
        findings["notes"].append(
            "nuclei scan skipped (pass --allow-nuclei only if the program's "
            "policy permits automated scanning)."
        )

    out_path = out_path or f"recon_{domain.replace('.', '_')}.json"
    with open(out_path, "w") as f:
        json.dump(findings, f, indent=2)

    print(f"\nRecon summary written to {out_path}")
    print(f"Subdomains found: {len(findings['subdomains'])}")
    print(f"Alive hosts probed: {len(findings['alive_hosts'])}")
    if findings["notes"]:
        print("\nNotes:")
        for n in findings["notes"]:
            print(f"  - {n}")

    return findings
