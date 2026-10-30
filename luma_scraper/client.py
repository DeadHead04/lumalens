import json
import math
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote, urlparse
from zoneinfo import ZoneInfo

import httpx


class LumaError(RuntimeError):
    def __init__(self, code, message, status=None):
        super().__init__(message)
        self.code, self.status = code, status


def instant(value, zone="UTC"):
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (result if result.tzinfo else result.replace(tzinfo=ZoneInfo(zone))).astimezone(timezone.utc)


def window(entries, start=None, end=None, zone="UTC"):
    lo, hi = instant(start, zone) if start else None, instant(end, zone) if end else None
    if lo and hi and lo >= hi:
        raise ValueError("--from must be earlier than --to (exclusive)")
    result = []
    for row in entries:
        event = row.get("event", row)
        date = event.get("start_at") or row.get("start_at")
        if not date:
            if not lo and not hi:
                result.append(row)
            continue
        stamp = instant(date)
        if (lo is None or stamp >= lo) and (hi is None or stamp < hi):
            result.append(row)
    return result


def distance_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a["latitude"], a["longitude"], b["latitude"], b["longitude"]])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


class LumaClient:
    API = "https://api.lu.ma"
    WEB = "https://luma.com"

    def __init__(self, cookies=None, *, timeout=30, retries=3, interval=0.35, transport=None):
        self.http = httpx.Client(cookies=cookies, timeout=timeout, follow_redirects=False, transport=transport,
                                 headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": self.WEB,
                                          "Referer": self.WEB + "/", "x-luma-client-type": "luma-web"})
        self.retries, self.interval, self.last_request = retries, interval, 0.0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.http.close()

    def _get(self, url, params=None):
        for attempt in range(self.retries + 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.http.get(url, params=params)
            except httpx.TransportError:
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
                raise LumaError("NETWORK", "Luma request failed or timed out") from None
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.retries:
                    raw = response.headers.get("retry-after", "")
                    try:
                        delay = float(raw)
                    except ValueError:
                        try:
                            delay = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
                        except (ValueError, TypeError):
                            delay = 2 ** attempt
                    if delay > 60:
                        raise LumaError("RATE_LIMITED", "Server requested a long pause; retry later", response.status_code)
                    time.sleep(max(0, delay))
                    continue
            if not response.is_success:
                code = {401: "AUTH_REQUIRED", 403: "FORBIDDEN", 429: "RATE_LIMITED", 404: "NOT_FOUND"}.get(response.status_code, "API_ERROR")
                raise LumaError(code, f"Luma returned HTTP {response.status_code} ({code}); check session, event access, or parameters", response.status_code)
            return response
        raise AssertionError("unreachable")

    def request(self, path, **params):
        if not path.startswith("/") or path.startswith("//") or "?" in path:
            raise ValueError("Use a relative API path and keyword query parameters")
        response = self._get(self.API + path, {k: v for k, v in params.items() if v is not None})
        try:
            data = response.json()
        except ValueError:
            raise LumaError("SCHEMA_CHANGED", "Expected JSON; Luma may require browser verification") from None
        if not isinstance(data, dict):
            raise LumaError("SCHEMA_CHANGED", "Expected a JSON object")
        return data

    def _page_data(self, slug):
        response = self._get(self.WEB + "/" + quote(slug, safe="/"))
        match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.S)
        if not match:
            raise LumaError("SCHEMA_CHANGED", "Luma page no longer contains expected structured data")
        try:
            return json.loads(match[1])["props"]["pageProps"]["initialData"]
        except (ValueError, KeyError):
            raise LumaError("SCHEMA_CHANGED", "Unexpected Luma page data") from None

    def paginate(self, path, *, max_pages=100, page_size=100, **params):
        if not 1 <= page_size <= 100 or max_pages < 1:
            raise ValueError("page_size must be 1–100 and max_pages positive")
        entries, ids, cursors, cursor = [], set(), set(), None
        for page in range(1, max_pages + 1):
            data = self.request(path, pagination_limit=page_size, pagination_cursor=cursor, **params)
            rows = data.get("entries")
            if not isinstance(rows, list) or not isinstance(data.get("has_more"), bool) or any(not isinstance(row, dict) for row in rows):
                raise LumaError("SCHEMA_CHANGED", "Invalid paginated response; refusing to report an empty success")
            for row in rows:
                identity = row.get("api_id") or row.get("event", {}).get("api_id") or row.get("user", {}).get("api_id")
                if identity is None or identity not in ids:
                    entries.append(row)
                    if identity:
                        ids.add(identity)
            if not data["has_more"]:
                return dict(entries=entries, complete=True, pages=page, next_cursor=None)
            next_cursor = data.get("next_cursor")
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in cursors:
                raise LumaError("PAGINATION_STALLED", "Missing or repeated cursor; collection is incomplete")
            cursors.add(next_cursor)
            cursor = next_cursor
        return dict(entries=entries, complete=False, pages=max_pages, next_cursor=cursor)

    def place(self, city):
        slug = city.strip().lower().replace(" ", "-")
        slug = {"bangalore": "bengaluru", "sf": "sf", "san-francisco": "sf", "nyc": "nyc", "new-york": "nyc"}.get(slug, slug)
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            raise ValueError("Use the city's Luma slug, such as bengaluru or london")
        initial = self._page_data(slug)
        if initial.get("kind") != "discover-place":
            raise LumaError("UNSUPPORTED_CITY", "This city has no Luma discovery page; supply a supported Luma city slug")
        return initial["data"]["place"]

    def discover(self, city, *, start=None, end=None, zone=None, radius_km=None, max_pages=100, page_size=50):
        place = self.place(city)
        zone = zone or place.get("timezone", "UTC")
        # Discovery has no historical inventory. Never silently claim past coverage.
        window([], start, end, zone)
        if start and instant(start, zone).astimezone(ZoneInfo(zone)).date() < datetime.now(ZoneInfo(zone)).date():
            raise LumaError("HISTORY_UNSUPPORTED", "City discovery only exposes current/upcoming events. Use history for your account's past events.")
        if end and instant(end, zone) <= datetime.now(timezone.utc):
            raise LumaError("HISTORY_UNSUPPORTED", "Past city discovery is unavailable; use account history")
        result = self.paginate("/discover/get-paginated-events", discover_place_api_id=place["api_id"], max_pages=max_pages, page_size=page_size)
        result["entries"] = window(result["entries"], start, end, zone)
        if radius_km is not None:
            if radius_km <= 0:
                raise ValueError("Radius must be positive")
            result["entries"] = [e for e in result["entries"] if e.get("event", {}).get("coordinate") and distance_km(place["coordinate"], e["event"]["coordinate"]) <= radius_km]
        result.update(city=place["name"], timezone=zone, coverage="Luma discovery feed only; not every event in the city", count=len(result["entries"]))
        return result

    def me(self):
        data = self.request("/user")
        if not data.get("user") and not data.get("api_id"):
            raise LumaError("AUTH_REQUIRED", "No authenticated Luma user; create or refresh your saved session")
        return data

    def history(self, *, period="past", start=None, end=None, zone="UTC", max_pages=100, page_size=50):
        if period not in {"past", "future"}:
            raise ValueError("period must be past or future")
        self.me()
        window([], start, end, zone)
        result = self.paginate("/home/get-events", period=period, max_pages=max_pages, page_size=page_size)
        result["entries"] = window(result["entries"], start, end, zone)
        result["count"] = len(result["entries"])
        result["coverage"] = "Account events, including invitations; registration does not prove attendance"
        return result

    def event(self, reference):
        ticket = None
        if reference.startswith(("http://", "https://")):
            parsed = urlparse(reference)
            if parsed.scheme != "https" or parsed.hostname not in {"luma.com", "www.luma.com", "lu.ma"} or parsed.username or parsed.password:
                raise ValueError("Expected an HTTPS Luma event URL")
            reference = parsed.path.strip("/")
            ticket = parse_qs(parsed.query).get("tk", [None])[0]
        if reference.startswith("event/"):
            reference = reference[6:]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", reference):
            raise ValueError("Expected event ID, slug, or Luma event URL")
        if reference.startswith("evt-"):
            event_id = reference
        else:
            initial = self._page_data(reference)
            if initial.get("kind") != "event":
                raise ValueError("URL is not a Luma event")
            event_id = initial["data"].get("event", {}).get("api_id") or initial["data"].get("api_id")
        if not event_id:
            raise LumaError("SCHEMA_CHANGED", "Event ID missing")
        details = self.request("/event/get", event_api_id=event_id, referring_ticket_key=ticket)
        ticket = ticket or (details.get("guest_data") or {}).get("ticket_key")
        return event_id, ticket, details

    def guests(self, reference, *, max_pages=100, page_size=100):
        event_id, ticket, details = self.event(reference)
        result = self.paginate("/event/get-guest-list", event_api_id=event_id, ticket_key=ticket, max_pages=max_pages, page_size=page_size)
        result.update(event_api_id=event_id, event_name=details.get("event", {}).get("name"), count=len(result["entries"]),
                      coverage="Only guest fields visible to this session or ticket; hidden contact details are not available")
        return result
