# CLI and Python reference

Standalone Python library and CLI for Luma city discovery, account event history,
and guest lists visible to a saved session. Collection uses JSON API requests;
a browser is only needed to create a session. Unofficial web endpoints may change.

## Install

Python 3.11+ is required. From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[chrome,login]'
luma-scraper --help
```

The `login` extra uses an installed Google Chrome. No separate Chromium download
is required. The core package requires httpx and tzdata. Install the generated wheel
from `dist/` on another machine with `pip install /path/to/package.whl`.

## Saved sessions

Sign in once, then reuse the session for every API call:

```sh
luma-scraper login --save .sessions/my-account.json
luma-scraper whoami --session .sessions/my-account.json
```

The login command opens an isolated Chrome window. Complete login yourself; the
command verifies `/user`, saves Luma cookies only, and closes its browser. It does
not change your existing Chrome profile. Session files use owner-only permissions on POSIX systems
(Windows uses directory ACLs) and are excluded from Git and distribution builds. Use a different filename for
each account. When a session expires, run login again with a new filename.

`--session` also accepts a Playwright storage-state JSON, a browser cookie array,
a JSON cookie name/value map (explicitly treated as Luma API cookies), or a Netscape
cookie file. Domain-bearing files are filtered to Luma domains; expired cookies
are ignored. Local storage and other sites' cookies are not imported.

Direct Chrome profile access is optional:

```sh
luma-scraper whoami --chrome-profile 'Profile 1'
luma-scraper whoami --chrome-profile 'you@example.com'
```

This depends on OS decryption permissions. macOS Keychain prevented direct cookie
decryption on the development machine; the separate login flow was verified instead.
Neither session tokens nor ticket keys are printed by the CLI.

## City events and date ranges

```sh
luma-scraper discover --city Bengaluru \
  --from 2026-10-30 --to 2026-11-07 \
  --out exports/bengaluru.json

luma-scraper discover --city london --radius-km 25 \
  --format csv --out exports/london.csv
```

Use a city's Luma discovery slug (for example `bengaluru`, `london`, `sf`, `nyc`).
`Bangalore` is an alias for Bengaluru. There is no hardcoded city coordinate list:
the package resolves the current city page and its discovery-place ID. It rejects
unknown/unsupported pages. Date-only and naive times use the city's timezone;
`--timezone Asia/Kolkata` overrides it. Offset-aware timestamps also work.
`--from` is inclusive; `--to` is exclusive, so November 7 includes events through
November 6. Filtering is by event start time, not overlap duration.

**Limits verified live:** the current city API requires `discover_place_api_id`.
The coordinate-only request in the original notes returns HTTP 400. The API also
rejects `period=past`. This package therefore supports current/upcoming discovery
in Luma-supported cities, not arbitrary global cities or historical city archives.
Past date windows fail explicitly; use account history for past registrations.
The feed is curated and cannot guarantee every event in a city. A radius is a
local filter around the city's center within this feed, not a wider geographic
search; entries lacking coordinates are excluded when that filter is supplied.
Missing price/availability fields remain unknown in the returned data.

## Past and upcoming account events

```sh
luma-scraper history --session .sessions/my-account.json \
  --period past --out exports/past-events.json

luma-scraper history --session .sessions/my-account.json \
  --period future --from 2026-11-01 --to 2026-12-01 \
  --timezone Asia/Kolkata --out exports/upcoming.json
```

History includes invitations and pending approvals, not just registrations.
`entry.guest_info.approval_status == "approved"` identifies approved registrations;
it does not prove physical attendance. History defaults to UTC for date filtering.

## Export a guest list

```sh
luma-scraper guests --session .sessions/my-account.json \
  --event https://luma.com/YOUR-EVENT-SLUG \
  --format csv --out exports/guests.csv
```

An `evt-…` API ID or event slug also works. The client retrieves event details,
uses your account's ticket key when returned, then paginates the guest endpoint.
Names, bios, profile links and social handles are retained only when returned by
Luma. It cannot obtain hidden email addresses, phone numbers, or organizer-only
fields. Registration does not override the organizer's guest-list visibility.
401/403 responses are reported as errors, not empty guest lists.

A registered ticket URL copied from Luma can also work without a session. Treat
it as a secret: store it in a private local file and use `--event-file` to avoid
putting its query string in shell history:

```sh
luma-scraper guests --event-file .sessions/event-link.txt \
  --out exports/event-guests.json
```

## Python API

```python
from luma_scraper import LumaClient, load_session

with LumaClient(cookies=load_session('.sessions/my-account.json')) as client:
    events = client.discover('bengaluru')
    past = client.history(period='past')
    guests = client.guests('https://luma.com/YOUR-EVENT-SLUG')
    print(guests['count'], guests['complete'])
```

To fetch lists for approved past registrations, inspect history and call `guests`
for each event. Handle `LumaError` per event because visibility can differ:

```python
from luma_scraper import LumaError

# Inside the client context above:
for entry in past['entries']:
    if (entry.get('guest_info') or {}).get('approval_status') != 'approved':
        continue
    try:
        result = client.guests(entry['event']['api_id'])
        # Save result locally; check result['complete'] before treating it as complete.
    except LumaError as error:
        print(entry['event']['api_id'], error.code)
```

## Pagination, exports, and errors

- All pages are fetched by default, capped at 100 pages. Use `--max-pages` and
  `--page-size` to configure this. A cap produces `complete: false`, a warning,
  and CLI exit code 2. Increase the cap and rerun to fetch more.
- Repeated/missing cursors and malformed responses fail explicitly. Entries are
  deduplicated by API ID. There is no assumption that API pages are date-sorted.
- Default request spacing is 350 ms, timeout 30 seconds, with up to three retries
  for transport errors, 429, and 5xx. Retry-After is honored; waits above 60 seconds
  return an error so the caller can retry later. Access denials are not retried.
- JSON retains entries and coverage metadata. CSV flattens event/user fields,
  encodes nested values as JSON, escapes spreadsheet formulas, and writes a
  `.csv.meta.json` sidecar with pagination and coverage information.
- Existing output files are never overwritten. On POSIX systems outputs use owner-only file permissions; on Windows, access follows your directory ACLs.
  Session and history exports can contain ticket keys: keep them private.
- Exit code 0 means successful collection within the endpoint's stated coverage;
  1 means an error; 2 means truncated results (or invalid command arguments).

## API contracts

The observed web contracts are `/discover/get-paginated-events` with
`discover_place_api_id`, `/home/get-events` with `period=past|future`, `/event/get`,
`/event/get-guest-list` with optional `ticket_key`, and `/user`, on `api.lu.ma`.
These are unofficial web endpoints, not a stable official SDK contract.
