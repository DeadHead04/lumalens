"""Scoped session import. Credentials never appear in diagnostics."""
import json
import math
import os
import sys
import time
from pathlib import Path

import httpx


def is_luma_domain(domain):
    return domain.lstrip(".").lower() in {"luma.com", "www.luma.com", "api.luma.com", "api2.luma.com", "lu.ma", "api.lu.ma"}


def load_session(path):
    """Read Playwright storageState, browser cookie JSON, or Netscape cookies."""
    text = Path(path).expanduser().read_text(encoding="utf-8-sig")
    cookies = httpx.Cookies()
    if text.lstrip().startswith(("{", "[")):
        data = json.loads(text)
        rows = data.get("cookies", data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = [{"name": k, "value": v, "domain": "api.lu.ma"} for k, v in rows.items()]
    else:
        rows = []
        for line in text.splitlines():
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 7:
                raise ValueError("Invalid Netscape cookie row")
            domain, _, path_, _, expires, name, value = fields
            rows.append(dict(domain=domain, path=path_, expires=float(expires), name=name, value=value))
    if not isinstance(rows, list):
        raise ValueError("Session must contain a cookie array or name/value object")
    for c in rows:
        if not isinstance(c, dict):
            raise ValueError("Cookie entries must be objects")
        domain = c.get("domain", "")
        expires = c.get("expires", c.get("expirationDate", -1))
        if not isinstance(domain, str) or (expires is not None and not isinstance(expires, (int, float))):
            raise ValueError("Invalid cookie domain or expiry")
        if not is_luma_domain(domain) or (expires and expires > 0 and expires <= time.time()):
            continue
        name, value = c.get("name"), c.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("Invalid cookie name/value")
        path_ = c.get("path", "/")
        if not name or any(ch in name + value for ch in "\r\n") or not isinstance(path_, str) or not path_.startswith("/"):
            raise ValueError("Invalid cookie name, value, or path")
        if expires is not None and not math.isfinite(expires):
            raise ValueError("Invalid cookie expiry")
        cookies.set(name, value, domain=domain, path=path_)
    # Luma's web session cookie is shared by its web and API clients across domains.
    auth = [c.value for c in cookies.jar if c.name == "luma.auth-session-key"]
    if auth:
        if len(set(auth)) != 1:
            raise ValueError("Session contains multiple Luma accounts; export one account at a time")
        cookies.set("luma.auth-session-key", auth[0], domain="api.lu.ma", path="/")
    if not list(cookies.jar):
        raise ValueError("No unexpired Luma cookies found")
    return cookies


def chrome_session(profile="Default", chrome_root=None):
    try:
        import browser_cookie3
    except ImportError:
        raise ValueError('Install the Chrome extra: pip install ".[chrome]"') from None
    roots = {
        "darwin": Path.home() / "Library/Application Support/Google/Chrome",
        "linux": Path.home() / ".config/google-chrome",
        "win32": Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data",
    }
    root = Path(chrome_root).expanduser() if chrome_root else roots.get(sys.platform)
    if root is None:
        raise ValueError("Provide chrome_root for this platform")
    state = root / "Local State"
    if state.exists():
        info = json.loads(state.read_text(encoding="utf-8-sig")).get("profile", {}).get("info_cache", {})
        matches = [k for k, v in info.items() if profile.casefold() in {k.casefold(), v.get("name", "").casefold(), v.get("user_name", "").casefold()}]
        if len(matches) > 1:
            raise ValueError("Ambiguous Chrome profile; use its Profile N directory name")
        if matches:
            profile = matches[0]
    if Path(profile).name != profile or profile in {".", ".."}:
        raise ValueError("Profile must be a directory name or account email")
    files = [root / profile / "Network/Cookies", root / profile / "Cookies"]
    path = next((p for p in files if p.exists()), None)
    if not path:
        raise ValueError("Chrome profile cookie database not found")
    cookies = httpx.Cookies()
    try:
        for domain in ("luma.com", "lu.ma"):
            jar = browser_cookie3.chrome(cookie_file=str(path), domain_name=domain)
            for c in jar:
                if is_luma_domain(c.domain) and not c.is_expired():
                    cookies.jar.set_cookie(c)
    except Exception:
        raise ValueError("Chrome cookies could not be decrypted. Use 'login' or --session with an exported cookie file.") from None
    auth = {c.value for c in cookies.jar if c.name == "luma.auth-session-key"}
    if len(auth) != 1:
        raise ValueError("No single active Luma login in this Chrome profile; use 'login'")
    cookies.set("luma.auth-session-key", auth.pop(), domain="api.lu.ma", path="/")
    return cookies


def save_private_json(path, data):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def login(path, timeout=300):
    """User signs in interactively in an isolated Chrome window."""
    from playwright.sync_api import sync_playwright, Error as BrowserError
    from .client import LumaClient, LumaError
    if timeout <= 0:
        raise ValueError("Login timeout must be positive")
    if Path(path).expanduser().exists():
        raise ValueError("Session file already exists; choose a new filename")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=False)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://luma.com/signin")
                print("Sign in to Luma in the new Chrome window. Waiting for a verified session…", file=sys.stderr)
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    rows = [c for c in context.cookies() if is_luma_domain(c["domain"])]
                    auth = next((c for c in rows if c["name"] == "luma.auth-session-key"), None)
                    if auth:
                        cookies = httpx.Cookies()
                        cookies.set(auth["name"], auth["value"], domain="api.lu.ma")
                        try:
                            with LumaClient(cookies=cookies) as client:
                                client.me()
                        except LumaError:
                            pass
                        else:
                            save_private_json(path, {"cookies": rows, "origins": []})
                            return
                    page.wait_for_timeout(1500)
                raise ValueError("Login timed out; no session saved")
            finally:
                browser.close()
    except BrowserError:
        raise ValueError("Login browser failed or was closed. Install Google Chrome and retry login on a graphical desktop.") from None
