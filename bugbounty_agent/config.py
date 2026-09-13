"""
Shared config/helpers for the bug bounty agent.
"""
import os
import shutil
import sys

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# External recon tools this project can orchestrate IF you have them installed.
# We never bundle or auto-install exploit tools — you choose what's on your machine.
KNOWN_TOOLS = ["subfinder", "httpx", "nuclei", "nmap", "whatweb"]


def which_tools():
    """Return dict of tool_name -> path or None, for whatever's on PATH."""
    return {t: shutil.which(t) for t in KNOWN_TOOLS}


def require_authorization():
    """
    Hard stop unless the user explicitly confirms they are authorized to test
    the target (e.g. it's their own asset, or in-scope on a bug bounty program
    like HackerOne/Bugcrowd/Intigriti). This is a real gate, not a formality —
    testing systems without authorization is illegal in most jurisdictions.
    """
    print("\n=== Authorization check ===")
    print("Before scanning anything, confirm ONE of the following is true:")
    print("  1. You own this target/asset, OR")
    print("  2. It is explicitly in-scope on a bug bounty program you're enrolled in")
    print("     (HackerOne, Bugcrowd, Intigriti, YesWeHack, or a private program), OR")
    print("  3. You have written permission from the asset owner.")
    ans = input("Type 'yes' to confirm one of the above applies to this target: ").strip().lower()
    if ans != "yes":
        print("Authorization not confirmed. Exiting.")
        sys.exit(1)
    return True
