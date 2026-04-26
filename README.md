# NBP Booster Club Enrichment Agent

Weekly Claude-based agent that finds missing public contact info for school athletic booster clubs in the Carolinas. Updates `dashboard-data.json` in [`nbp-school-proposals`](https://github.com/nathangbingle/nbp-school-proposals) so the dashboard at [nathangbingle.github.io/nbp-school-proposals/booster-dashboard.html](https://nathangbingle.github.io/nbp-school-proposals/booster-dashboard.html) picks up the new data on next refresh.

## What changed (April 2026)

The old version of this agent scraped DuckDuckGo HTML and got rate-limited into uselessness (last run before replacement: 0 found / 12 blocked). This rewrite uses the Anthropic API's built-in `web_search` tool — no scraping, no IP blocks, structured output.

| | Old agent | New agent |
|---|---|---|
| Search | DuckDuckGo HTML scraping | Anthropic `web_search` tool |
| Cadence | Daily | Weekly (Sundays 3am ET) |
| Cost | Free, but broken | ~$1.20/run, ~$5/month |
| Output | FB URL only | FB, Instagram, email, AD, website, activity |
| Reliability | Rate-limited | Production-grade |

## How it works

1. Pulls live `dashboard-data.json` from GitHub raw
2. For each club with gaps (FB, IG, email, AD, website, or activity), calls Claude Haiku 4.5 with the `web_search` tool (max 5 searches per club)
3. Claude returns strict JSON with verified fields only — never fabricates
4. Updates apply without overwriting existing real values
5. Tracks `last_enrichment_attempted` + `enrichment_misses` per club; clubs that strike out 3+ times move to quarterly retry to save cost
6. Commits a summary back to `nathangbingle/nbp-school-proposals`

## Env vars

| Var | Required | Default | What it is |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | — | Anthropic API key (sk-ant-…) |
| `GITHUB_TOKEN` | yes | — | PAT with `repo` scope |
| `GITHUB_REPO` | no | `nathangbingle/nbp-school-proposals` | Repo holding the data file |
| `DATA_PATH` | no | `dashboard-data.json` | File path in the repo |
| `MODEL` | no | `claude-haiku-4-5-20251001` | Bump to Sonnet for harder cases |
| `COOLDOWN_DAYS` | no | `14` | Skip clubs attempted within N days |
| `MAX_CLUBS` | no | `30` | Cap clubs per run (cost control) |
| `DRY_RUN` | no | `0` | Set to `1` to skip the commit/push |

## Cost

Roughly **$1–2 per run**, ~$5/month at weekly cron:
- ~30 clubs × ~3 web searches each = ~90 searches × $10/1000 = **$0.90**
- ~5K input tokens × 30 + ~1K output × 30 ≈ **$0.30** on Haiku 4.5
- Free Railway tier covers compute (job runs <2 min)

After 1–2 runs, costs drop further — clubs that have permanent gaps (no public FB exists) move to quarterly retry, so we stop wasting searches on them.

## Cron schedule

Configured in `railway.json` as `0 7 * * 0` — every Sunday at 07:00 UTC = 3:00am ET.

To change: edit `railway.json`, push, Railway picks it up automatically.

## Local test

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export DRY_RUN=1
export MAX_CLUBS=2
python enrich.py
```

## What it will NOT do

- It won't invent URLs or emails. If Claude can't verify it, the field stays null.
- It won't overwrite an existing real value.
- It won't discover NEW clubs — only enriches the existing 30 in the data file.
- It won't run on `excluded` clubs (e.g. PKMS, the existing client).

## Watching it work

After each run, the latest commit in `nbp-school-proposals` shows what changed:

```
Weekly enrichment: 4 clubs / 7 fields

cuthhs: +fb,activity
crest: +fb
hough: +email
ilms: +fb,ad
```

→ https://github.com/nathangbingle/nbp-school-proposals/commits/main
