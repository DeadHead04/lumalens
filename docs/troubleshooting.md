# Troubleshooting

| Symptom | What to do |
| --- | --- |
| `python` is missing | macOS/Linux: use `python3` to create the environment. Windows: install Python 3.11+ and use `py -3`. |
| `No module named luma_scraper` | Install the project with the same Python interpreter you are running. Activate `.venv` or use its Python by full path. |
| `luma-scraper` command missing | Use `python -m luma_scraper`; it is the same CLI. |
| Chrome executable missing during login | Install Google Chrome from its official vendor, then rerun. The login flow selects the installed Chrome channel. |
| No desktop/display on Linux | Log in on a desktop and privately transfer the resulting session to your server. |
| Chrome cookies could not be decrypted | Use the `login` command instead of `--chrome-profile`. OS Keychain protections can prevent direct reads. |
| Login timeout | Run again with `--timeout 600`; complete sign-in in the new window and wait for confirmation. |
| `AUTH_REQUIRED` / HTTP 401 | Verify with `whoami`. Create a fresh session using a new filename. |
| `FORBIDDEN` / HTTP 403 | Verify your identity and event access in Luma. Guest-list visibility may be restricted even for registered users. |
| `NOT_FOUND` / HTTP 404 | Check the event URL or city discovery slug. Not every city has a Luma discovery page. |
| `HISTORY_UNSUPPORTED` | Public city discovery cannot retrieve past dates. Use account `history --period past`. |
| `RATE_LIMITED` / HTTP 429 | Wait before retrying; do not increase concurrency to evade the limit. |
| `SCHEMA_CHANGED` / `PAGINATION_STALLED` | The upstream contract may have changed. Update the package; if unresolved, open a sanitized bug report. |
| Output already exists | Choose a new output filename. Existing data is intentionally preserved. |
| Exit code 2 / `complete: false` | Increase `--max-pages` and rerun into a new output file. CLI argument errors also use exit code 2. |
| CSV and JSON show different shapes | CSV flattens user/event fields; nested objects become JSON strings. Pagination metadata is in `.csv.meta.json`. |
| Date filter seems shifted | Specify `--timezone`. City searches default to city time; history defaults to UTC. `--to` is exclusive. |

## Reporting a problem

Include your OS, Python version, package version, sanitized command, error code, and expected behavior. Use a public event URL only when appropriate. Do not attach cookies, ticket URLs containing `tk=`, raw history, guest exports, or screenshots containing credentials.

Run offline checks before reporting a development regression:

```sh
python -m unittest discover -s tests -v
```

These tests validate package behavior; passing tests cannot prove that the live upstream API has not changed. See [CONTRIBUTING.md](../CONTRIBUTING.md).
