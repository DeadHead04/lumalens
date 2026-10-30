# Luma Scraper — Python API & CLI

[![Tests](https://github.com/DeadHead04/luma-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/DeadHead04/luma-scraper/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Find upcoming Luma (lu.ma) events, download your event history, and export guest lists your account can access.** An API-first Python package and command-line tool with reusable login sessions, pagination, date filters, and JSON/CSV exports.

No API key is needed. Public discovery works without login. For private account data, each person signs into their own Luma account once and keeps the session on their own computer.

> Unofficial community project; not affiliated with Luma. City discovery covers Luma-supported cities and current/upcoming listings. It is not a historical archive or a way to access hidden guest information. Luma can change these web endpoints.

## What can I do with it?

| Use case | Command | Login? |
| --- | --- | --- |
| Find upcoming events in Bengaluru, London, or another supported city | `discover` | No |
| Filter events by date, timezone, and radius | `discover` | No |
| Download past registrations, invitations, and pending requests | `history --period past` | Yes |
| Download upcoming account events | `history --period future` | Yes |
| Export an event's visible guests and available social profiles | `guests` | Session or accessible ticket link |
| Verify which account a session belongs to | `whoami` | Yes |

## Quick start

You need **Python 3.11+**, **Git**, and **Google Chrome** for interactive login. Install them first if needed. No Chrome is required for public discovery alone.

### 1. Install

**macOS / Linux**

```sh
git clone https://github.com/DeadHead04/luma-scraper.git
cd luma-scraper
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[login]'
```

**Windows PowerShell**

```powershell
git clone https://github.com/DeadHead04/luma-scraper.git
cd luma-scraper
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[login]"
```

On Windows, replace `python` in the commands below with `.\.venv\Scripts\python.exe`. This avoids changing PowerShell's script-execution policy.

### 2. Try public event discovery

```sh
python -m luma_scraper discover --city bengaluru --out exports/events.json
```

This creates a local JSON export. Try `london`, `sf`, or `nyc`, or use the city slug from a Luma discovery page. Use `--format csv --out exports/events.csv` for a spreadsheet-friendly export.

### 3. Sign in with your own account

```sh
python -m luma_scraper login --save .sessions/my-account.json
```

A separate Chrome window opens. Complete your normal Luma login in that window. The tool waits up to five minutes, verifies your account, saves only Luma session cookies locally, then closes its browser. It does not ask you to paste a password into the terminal.

```sh
python -m luma_scraper whoami --session .sessions/my-account.json
```

Check that this shows the intended account. Keep the session file private. There is no shared account or hosted service.

### 4. Download your history or a guest list

```sh
python -m luma_scraper history --session .sessions/my-account.json --period past --out exports/my-history.json
```

Replace `YOUR-EVENT-SLUG` with your event's URL slug:

```sh
python -m luma_scraper guests --session .sessions/my-account.json --event https://luma.com/YOUR-EVENT-SLUG --format csv --out exports/guests.csv
```

CSV exports include a `.meta.json` sidecar showing whether pagination finished. Existing output files are never overwritten: choose a new filename on the next run.

## Date filtering

Use ISO dates or timestamps. `--from` is inclusive and `--to` is exclusive. Replace these illustrative dates with your desired current/future window:

```sh
python -m luma_scraper discover --city bengaluru --from 2027-01-01 --to 2027-02-01 --timezone Asia/Kolkata --out exports/january-events.json
```

A city search defaults to that city's timezone. Account history defaults to UTC. Filtering uses event start time. Historical **account events** are supported; historical **city discovery** is not.

For a rolling window without editing dates, see [the next-seven-days Python example](examples/discover_next_week.py).

## Use as a Python library

```python
from luma_scraper import LumaClient, load_session

with LumaClient() as client:
    events = client.discover("bengaluru")
    print(events["count"], events["complete"])

with LumaClient(cookies=load_session(".sessions/my-account.json")) as client:
    past = client.history(period="past")
    guests = client.guests("https://luma.com/YOUR-EVENT-SLUG")
```

Check `complete` before treating a result as a complete collection. The default cap is 100 pages. The CLI returns exit code **2** for a capped result; increase `--max-pages` and rerun.

## Documentation

- [Setup, login, multiple accounts, servers, and upgrades](docs/setup.md)
- [Use cases and runnable examples](docs/use-cases.md)
- [Complete CLI and Python reference](docs/reference.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributing and development](CONTRIBUTING.md)
- [Security and private data](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Release downloads](https://github.com/DeadHead04/luma-scraper/releases)

## Limits to understand

- The discovery feed is curated. It does not include every event in every city.
- Past date windows for city discovery are unsupported by the current API.
- Being registered does not guarantee guest-list access. Host visibility settings still apply.
- Only fields Luma returns are exported. Hidden emails, phone numbers, and organizer-only records are not unlocked.
- History includes invitations and pending approvals. Registration does not prove attendance.
- Sessions can expire. Log in again with a new session filename when needed.
- Unofficial endpoints can change. Releases and regression tests help maintain compatibility, but no tool can promise permanent access.

## Development

```sh
python -m pip install -e '.[dev,login]'
python -m unittest discover -s tests -v
python -m build
```

CI tests Python 3.11 and 3.14 on Linux, macOS, and Windows without credentials or live API calls. Live login, discovery, history, and guest pagination were checked on macOS on October 30, 2026; other live platforms are not yet verified.

MIT licensed. Use your own account and handle exported guest data responsibly. Issues and pull requests are welcome—please remove cookies, ticket keys, and personal guest data before sharing diagnostics.
