# NBP Booster Club Discovery Agent

Runs on Railway daily. For each school in `dashboard-data.json` (over in `nbp-school-proposals`) that doesn't yet have a Facebook URL, searches the public web and fills one in. Commits updated JSON back to the repo so the dashboard picks it up on next load.

## Env vars

| Var | Required | Default | What it is |
|---|---|---|---|
| `GITHUB_TOKEN` | yes | — | PAT with `repo` scope |
| `GITHUB_REPO` | no | `nathangbingle/nbp-school-proposals` | Repo that holds the data file |
| `BRANCH` | no | `main` | Branch to commit to |
| `FILE_PATH` | no | `dashboard-data.json` | File path in the repo |

## Cron schedule

Railway service is configured to run daily at 12:00 UTC (~7am ET). Idempotent — re-running without new findings just bumps the version number.

## Local run

```bash
export GITHUB_TOKEN=ghp_xxx
pip install -r requirements.txt
python agent.py
```
