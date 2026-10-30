"""Discover events over the next seven days; no session required."""
import argparse
from datetime import datetime, timedelta, timezone

from luma_scraper import LumaClient, LumaError
from luma_scraper.cli import output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city', default='bengaluru')
    parser.add_argument('--out', default='exports/next-week.json')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        with LumaClient() as client:
            result = client.discover(args.city, start=now, end=now + timedelta(days=7))
        output(result, args.out)
        return 0 if result['complete'] else 2
    except (LumaError, OSError, ValueError) as error:
        print(f'Export failed: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
