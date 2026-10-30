import argparse
import csv
import io
import json
import os
import sys
from pathlib import Path

from .client import LumaClient, LumaError, object_value
from .sessions import chrome_session, load_session, login


def safe_cell(value):
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_text(result):
    rows = []
    for entry in result.get("entries", []):
        if "user" in entry:
            row = {"guest_api_id": entry.get("api_id"), **object_value(entry["user"]), "section_label": entry.get("section_label"),
                   "num_tickets_registered": entry.get("num_tickets_registered")}
        else:
            row = dict(object_value(entry.get("event", entry)))
            for key in ("ticket_info", "registration_availability", "guest_info"):
                if key in entry:
                    row[key] = entry[key]
        rows.append(row)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows({k: safe_cell(v) for k, v in row.items()} for row in rows)
    return stream.getvalue()


def output(result, path=None, format="json"):
    text = csv_text(result) if format == "csv" else json.dumps(result, indent=2, ensure_ascii=False)
    if not path:
        print(text)
        return
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payloads = [(destination, text)]
    if format == "csv":
        meta = destination.with_suffix(destination.suffix + ".meta.json")
        payloads.append((meta, json.dumps({k: v for k, v in result.items() if k != "entries"}, indent=2)))
    created = []
    try:
        for target, content in payloads:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(target)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(content)
    except BaseException:
        # Remove only files this invocation created; preserve pre-existing files.
        for target in created:
            target.unlink(missing_ok=True)
        raise
    print(f"Saved {result.get('count', len(result.get('entries', [])))} records to {destination}", file=sys.stderr)


def parser():
    p = argparse.ArgumentParser(description="API-first Luma discovery and authorized guest exports")
    sub = p.add_subparsers(dest="command", required=True)
    auth = sub.add_parser("login", help="Sign in once in a separate Chrome window")
    auth.add_argument("--save", required=True)
    auth.add_argument("--timeout", type=int, default=300)
    for command in ("discover", "history", "guests", "whoami"):
        cmd = sub.add_parser(command)
        session = cmd.add_mutually_exclusive_group()
        session.add_argument("--session", help="Cookie JSON, Playwright storageState, or Netscape cookie file")
        session.add_argument("--chrome-profile", help="Chrome profile directory, name, or email")
        cmd.add_argument("--out")
        cmd.add_argument("--format", choices=["json", "csv"], default="json")
        if command != "whoami":
            cmd.add_argument("--max-pages", type=int, default=100)
            cmd.add_argument("--page-size", type=int, default=50 if command != "guests" else 100)
        if command in {"discover", "history"}:
            cmd.add_argument("--from", dest="start")
            cmd.add_argument("--to", dest="end", help="Exclusive upper bound")
            cmd.add_argument("--timezone", dest="zone")
        if command == "discover":
            cmd.add_argument("--city", required=True, help="Luma city name or slug")
            cmd.add_argument("--radius-km", type=float)
        if command == "history":
            cmd.add_argument("--period", choices=["past", "future"], default="past")
        if command == "guests":
            cmd.add_argument("--event", help="Event ID, slug, or registered ticket URL")
            cmd.add_argument("--event-file", help="File containing a ticket URL (avoids shell history)")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command == "login":
            login(args.save, args.timeout)
            print(f"Verified session saved to {args.save}")
            return 0
        cookies = load_session(args.session) if args.session else chrome_session(args.chrome_profile) if args.chrome_profile else None
        with LumaClient(cookies=cookies) as client:
            if args.command == "whoami":
                data = client.me()
                user = data.get("user", data)
                result = {k: user[k] for k in ("api_id", "name", "email", "username") if k in user}
                if args.format == "csv":
                    raise ValueError("whoami supports JSON only")
            else:
                paging = dict(max_pages=args.max_pages, page_size=args.page_size)
                if args.command == "discover":
                    result = client.discover(args.city, start=args.start, end=args.end, zone=args.zone, radius_km=args.radius_km, **paging)
                elif args.command == "history":
                    result = client.history(period=args.period, start=args.start, end=args.end, zone=args.zone or "UTC", **paging)
                else:
                    if bool(args.event) == bool(args.event_file):
                        raise ValueError("Supply exactly one of --event or --event-file")
                    reference = Path(args.event_file).expanduser().read_text(encoding="utf-8").strip() if args.event_file else args.event
                    result = client.guests(reference, **paging)
            output(result, args.out, args.format)
            if result.get("complete") is False:
                print("WARNING: Page cap reached; export is incomplete. Raise --max-pages.", file=sys.stderr)
                return 2
        return 0
    except LumaError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    except (ValueError, OSError, ImportError) as exc:
        # Do not print arbitrary file contents or HTTP request URLs with ticket keys.
        if isinstance(exc, OSError):
            message = "Could not read/write file (output must not already exist)"
        elif isinstance(exc, ImportError):
            message = 'Optional dependency missing. Install with pip install ".[chrome,login]"'
        else:
            message = str(exc) if not isinstance(exc, json.JSONDecodeError) else "Invalid session JSON"
        print(f"Error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
