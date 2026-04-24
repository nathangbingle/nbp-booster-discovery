"""
NBP Booster Club Discovery Agent
--------------------------------
Runs on Railway cron (daily at 7am ET).

For each school in dashboard-data.json without a Facebook URL, searches
DuckDuckGo HTML for the school's athletic booster club and extracts the
first facebook.com page URL found. Writes results back to the repo.

Env vars required:
  GITHUB_TOKEN    - Personal access token with repo scope
  GITHUB_REPO     - Repo in the form "owner/name" (default: nathangbingle/nbp-school-proposals)
  BRANCH          - Branch to commit to (default: main)
  FILE_PATH       - Path to data JSON in repo (default: dashboard-data.json)
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import httpx
from bs4 import BeautifulSoup


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "nathangbingle/nbp-school-proposals")
BRANCH = os.environ.get("BRANCH", "main")
FILE_PATH = os.environ.get("FILE_PATH", "dashboard-data.json")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

SEARCH_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------- GitHub I/O ----------

def gh_headers() -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN env var is not set")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_file_from_github(client: httpx.Client) -> tuple[dict, str]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    resp = client.get(url, params={"ref": BRANCH}, headers=gh_headers(), timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(content), payload["sha"]


def commit_file_to_github(client: httpx.Client, data: dict, sha: str, message: str) -> None:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    body = {
        "message": message,
        "content": base64.b64encode(
            json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("ascii"),
        "sha": sha,
        "branch": BRANCH,
    }
    resp = client.put(url, json=body, headers=gh_headers(), timeout=60)
    if resp.status_code not in (200, 201):
        print(f"Commit failed: {resp.status_code} {resp.text}", file=sys.stderr)
        resp.raise_for_status()


# ---------- Search ----------

DDG_ENDPOINT = "https://html.duckduckgo.com/html/"

# Facebook URL patterns we want to catch
FB_URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?facebook\.com/(?:p/|pages/|profile\.php\?id=)?[^\s\"'<>]+",
    re.IGNORECASE,
)

# Patterns to exclude — generic FB pages, search, login, etc.
FB_EXCLUDE = [
    "/login", "/recover", "/help", "/privacy", "/policies",
    "/gaming", "/watch", "/marketplace", "/business",
    "/sharer", "/plugins", "/tr?", "/tr/",
]


def ddg_search(client: httpx.Client, query: str) -> list[str]:
    """Return extracted result URLs for a query."""
    try:
        resp = client.post(
            DDG_ENDPOINT,
            data={"q": query},
            headers=SEARCH_HEADERS,
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  search error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.select("a.result__a, a.result__url"):
        href = a.get("href", "")
        if not href:
            continue
        # DDG wraps results in a redirect like /l/?uddg=<encoded>
        if href.startswith("//duckduckgo.com/l/") or href.startswith("/l/"):
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                links.append(unquote(qs["uddg"][0]))
                continue
        links.append(href)
    return links


def extract_facebook_url(urls: list[str]) -> str | None:
    for url in urls:
        if "facebook.com" not in url.lower():
            continue
        if any(x in url.lower() for x in FB_EXCLUDE):
            continue
        # Skip bare facebook.com
        parsed = urlparse(url)
        if parsed.path in ("", "/"):
            continue
        # Clean up tracking params
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return clean
    return None


def discover_for_club(client: httpx.Client, club: dict) -> dict:
    """Return dict of fields to update on this club."""
    school = club.get("school") or club.get("name", "")
    queries = [
        f'"{school}" athletic booster club facebook',
        f'"{school}" booster club facebook',
        f'{school} athletic booster facebook',
    ]

    updates = {}
    for q in queries:
        print(f"  > {q}")
        urls = ddg_search(client, q)
        fb = extract_facebook_url(urls)
        if fb:
            updates["fb"] = fb
            updates["activity"] = "Discovered via search — verify manually"
            print(f"    ✓ found: {fb}")
            return updates
        time.sleep(1.5)  # Be polite between queries
    print("    ✗ no facebook.com URL found")
    return updates


# ---------- Main ----------

def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"=== NBP Booster Discovery Agent ===")
    print(f"Started: {started_at}")
    print(f"Repo: {GITHUB_REPO} (branch: {BRANCH})")
    print(f"File: {FILE_PATH}")
    print()

    with httpx.Client() as client:
        data, sha = fetch_file_from_github(client)
        print(f"Loaded {len(data.get('clubs', []))} clubs from GitHub.")

        discovered = 0
        total_missing = 0

        for club in data.get("clubs", []):
            if club.get("excluded"):
                continue
            if club.get("fb"):
                continue
            total_missing += 1
            print(f"\n[{club['id']}] {club['name']}")
            updates = discover_for_club(client, club)
            if updates:
                club.update(updates)
                discovered += 1

        print(f"\nDiscovered {discovered} of {total_missing} missing FB URLs.")

        # Update meta
        data.setdefault("meta", {})
        data["meta"]["last_discovery_run"] = started_at
        data["meta"]["last_updated"] = started_at
        data["meta"]["version"] = data["meta"].get("version", 1) + 1

        if discovered > 0:
            message = f"discovery agent: found {discovered} new FB pages"
        else:
            message = f"discovery agent: refresh run ({total_missing} still pending)"

        commit_file_to_github(client, data, sha, message)
        print(f"\nCommitted: {message}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
