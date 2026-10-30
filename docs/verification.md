# Release verification — v0.1.1

Verified on October 30, 2026. This records what was tested, not a guarantee of future upstream behavior.

## Offline regression suite

35 tests cover:

- Pagination, deduplication, missing/repeated cursors, and explicit page-cap results.
- HTTP access denials, rate-limit handling, timeouts, malformed JSON/page data, and credential-safe errors.
- CLI identity output, error codes, truncation exit code, and invalid arguments without unnecessary API requests.
- Timezone boundaries, including inclusive starts and exclusive ends.
- JSON/CSV writing, Unicode names, formula escaping, existing-file protection, and sidecar-conflict cleanup.
- Cookie domain/expiry filtering, BOM-prefixed JSON, malformed cookies, multiple accounts, and Netscape imports.
- Mocked login success, cookie filtering, timeout, browser cleanup, and browser-launch failure.
- Batch guest export selection and per-event permission failures.

CI runs the suite, CLI/example help checks, and builds on Python 3.11 and 3.14 on Linux, macOS, and Windows. Check the [Actions page](https://github.com/DeadHead04/lumalens/actions/workflows/ci.yml) for the exact release commit's result.

## Live read-only checks

15 checks were run on macOS with an authorized account. All passed:

| Check | Outcome |
| --- | --- |
| Saved-session identity | Account verified |
| Bengaluru discovery | 22 entries; complete feed pagination |
| London discovery | 53 entries; complete feed pagination |
| San Francisco discovery | 57 entries; complete feed pagination |
| New York discovery | 69 entries; complete feed pagination |
| City radius filter | Successful output |
| Past account events | Successful complete export |
| Upcoming account events | Successful export, including valid empty results |
| Guest JSON export | 213 entries across three pages |
| Guest CSV export | Same row count as JSON; complete metadata sidecar |
| Page cap | Exit 2 with `complete: false` |
| Unauthenticated history | Explicit error |
| Historical city discovery | Explicit unsupported error |
| Invalid timezone | Clean error, no traceback |
| Nonfinite radius | Clean error, no traceback |

Event totals are a snapshot and will change. Public discovery does not guarantee every event in a city. Guest exports were kept private; no live account data or session was added to the repository.

## Installation and packaging

The release process builds wheel/source archives, installs the wheel in a fresh virtual environment outside the checkout, checks CLI entry points and dependencies, and runs a public discovery request from that installed wheel. Source archives are checked for documentation/examples. Both archive formats are checked to exclude sessions and personal exports.

## Boundaries

- Interactive login was completed successfully on macOS earlier on the same date. This pass reused the saved session and tested login lifecycle failures offline; it did not ask the user to sign in again.
- Direct Chrome cookie decryption remained blocked by macOS Keychain. The supported alternative is the verified interactive-login flow.
- Live Windows/Linux login is not yet verified. Cross-platform CI covers offline behavior and packaging only.
- Rate limits, network timeouts, and malformed upstream payloads were exercised with synthetic responses, not by deliberately overloading Luma.
- Global arbitrary-city search, historical city discovery, and hidden guest information remain unsupported.
