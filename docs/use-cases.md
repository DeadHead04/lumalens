# Use cases

Run these commands from your installed checkout. Windows users can replace `python` with `.\.venv\Scripts\python.exe`.

## Find events to attend

```sh
python -m luma_scraper discover --city london --out exports/london.json
python -m luma_scraper discover --city bengaluru --radius-km 20 --format csv --out exports/nearby.csv
```

The radius filters coordinates within the city's discovery feed; it does not expand the feed or retrieve all events around an arbitrary location. Events without coordinates are excluded when a radius is used.

For a rolling week:

```sh
python examples/discover_next_week.py --city bengaluru --out exports/next-week.json
```

## Keep a copy of your registrations

```sh
python -m luma_scraper history --session .sessions/personal.json --period past --out exports/history.json
```

Each entry preserves `guest_info.approval_status`. `approved` indicates an approved registration, `invited` an invitation, and `pending_approval` a pending request. These are not check-in records.

## Export guests from one event

Replace the placeholder with an event you can access:

```sh
python -m luma_scraper guests --session .sessions/personal.json --event https://luma.com/YOUR-EVENT-SLUG --format csv --out exports/guests.csv
```

Available profile fields can include names, short bios, websites, and social handles. Availability varies by user and event. Never assume emails or phone numbers will be present.

## Export lists from approved past registrations

The included script fetches past history, selects approved registrations, and saves one JSON file per event:

```sh
python examples/export_registered_guests.py --session .sessions/personal.json --out-dir exports/registered-guests
```

It continues past individual event access errors and records success, failure, and pagination completeness in `summary.json`. It does not register you for events. Use a fresh output directory on each run. Large histories can take time; API throttling still applies.

## Work in a notebook or another Python application

```python
from luma_scraper import LumaClient, LumaError, load_session

with LumaClient(cookies=load_session('.sessions/personal.json')) as client:
    try:
        result = client.guests('evt-YOUR-EVENT-ID')
    except LumaError as error:
        print(error.code)  # AUTH_REQUIRED, FORBIDDEN, RATE_LIMITED, etc.
    else:
        for guest in result['entries']:
            print(guest.get('user', {}).get('name'))
        print('Complete:', result['complete'])
```

See [the reference](reference.md) for pagination controls, date semantics, and supported session formats.
