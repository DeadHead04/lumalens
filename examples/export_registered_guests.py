"""Export visible guests for approved past registrations; your own session required."""
import argparse
import re
from pathlib import Path

from luma_scraper import LumaClient, LumaError, load_session
from luma_scraper.cli import output


def collect(client, directory):
    directory = Path(directory)
    # Refuse an existing directory to avoid confusing an old and new run.
    directory.mkdir(parents=True, exist_ok=False)
    history = client.history(period='past')
    summary = {'history_complete': history['complete'], 'events': []}
    for entry in history['entries']:
        if (entry.get('guest_info') or {}).get('approval_status') != 'approved':
            continue
        event_id = entry['event']['api_id']
        if not re.fullmatch(r'evt-[A-Za-z0-9_-]+', event_id):
            summary['events'].append({'event_api_id': 'invalid', 'error': 'INVALID_EVENT_ID'})
            continue
        try:
            result = client.guests(event_id)
            output(result, directory / f'{event_id}.json')
            summary['events'].append({'event_api_id': event_id, 'count': result['count'], 'complete': result['complete']})
        except LumaError as error:
            summary['events'].append({'event_api_id': event_id, 'error': error.code})
    output(summary, directory / 'summary.json')
    return 0 if history['complete'] and all(e.get('complete') for e in summary['events']) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True)
    parser.add_argument('--out-dir', default='exports/registered-guests')
    args = parser.parse_args()
    try:
        with LumaClient(cookies=load_session(args.session)) as client:
            return collect(client, args.out_dir)
    except (LumaError, OSError, ValueError) as error:
        print(f'Export failed: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
