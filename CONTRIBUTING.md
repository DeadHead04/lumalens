# Contributing

Bug reports, documentation fixes, compatibility fixes, and focused pull requests are welcome.

## Development setup

```sh
git clone https://github.com/DeadHead04/lumalens.git
cd lumalens
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,login]'
python -m unittest discover -s tests -v
python -m build
```

On Windows use `.\.venv\Scripts\python.exe` instead of activating the environment.

## Make a change

1. Open an issue for a significant feature or behavior change.
2. Branch from `main` and keep the change focused.
3. Add meaningful offline tests with `httpx.MockTransport` for API behavior. Never commit live credentials or personal fixtures.
4. Update the relevant docs and `CHANGELOG.md`.
5. Run tests and build, then open a pull request explaining behavior and validation.

## Structure

- `luma_scraper/client.py`: API transport, retries, pagination, discovery, history, guests.
- `luma_scraper/sessions.py`: scoped cookie import and interactive login.
- `luma_scraper/cli.py`: arguments and private JSON/CSV export.
- `tests/`: offline regression tests.
- `examples/`: runnable workflows using your own account.
- `docs/`: setup, use cases, API reference, troubleshooting.

## Upstream compatibility

These are unofficial web APIs. When a response changes, reproduce it with your own authorized account, document the affected endpoint and sanitized schema, and add a regression test. Do not turn access errors into empty success or remove pagination completeness checks. Do not bypass visibility restrictions.

Never submit real cookie values, ticket keys, account history, or guest datasets. Synthetic fixtures should use clearly fake names and IDs.

## Releases (maintainers)

1. Update the package version and changelog.
2. Wait for CI to pass on the release commit.
3. Run `python -m build`; inspect wheel and source archive for unintended files.
4. Tag the commit `vX.Y.Z` and create a GitHub release with the wheel and source archive.
5. Document known upstream limitations. A release is not a guarantee of future API compatibility.

See [SECURITY.md](SECURITY.md) for private vulnerability reports. There is no guaranteed response-time or long-term maintenance SLA.
