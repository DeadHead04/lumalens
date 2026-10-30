# Setup and login

Start with the [README quick start](../README.md#quick-start).

## Installation choices

From the cloned repository:

| Need | Install command |
| --- | --- |
| Public discovery and already exported sessions | `python -m pip install .` |
| Interactive login (recommended) | `python -m pip install '.[login]'` |
| Read an existing Chrome profile where OS permissions allow it | `python -m pip install '.[chrome]'` |
| Everything plus development tools | `python -m pip install -e '.[login,chrome,dev]'` |

Use double quotes instead of single quotes if required by your shell. On Windows the README uses the virtual environment's Python directly; on macOS/Linux activate `.venv` first.

The package is distributed through this repository and GitHub Releases. It is **not currently published on PyPI**; do not assume a similarly named PyPI package is this project.

You can install a downloaded release wheel without cloning. Replace the filename with the wheel you downloaded:

```sh
python -m pip install './luma_session_scraper-0.1.1-py3-none-any.whl[login]'
```

## Interactive login

1. Install Google Chrome normally on your computer.
2. Run `python -m luma_scraper login --save .sessions/personal.json`.
3. Complete Luma's normal sign-in in the separate browser window, including any verification Luma requests.
4. Wait for the terminal to confirm that the session was verified and saved.
5. Run `python -m luma_scraper whoami --session .sessions/personal.json`.

The browser profile is temporary. Only Luma cookies are saved. Existing Chrome profiles remain unchanged. The tool never completes verification challenges for you.

If login takes longer, use `--timeout 600`. Close no browser window until the command finishes. A graphical desktop is required for this step; public discovery does not require one.

## Multiple accounts

Create one file for each account, logging into the intended account in each isolated window:

```sh
python -m luma_scraper login --save .sessions/personal.json
python -m luma_scraper login --save .sessions/work.json
python -m luma_scraper whoami --session .sessions/work.json
```

Choose the file with `--session` on each command. There is no global default account and no session is supplied in this repository. Session files must not contain conflicting accounts.

## Existing session files

Supported formats: Playwright `storage_state`, browser-exported cookie JSON arrays, Netscape cookie files, and explicit Luma name/value JSON maps. Only Luma cookies are imported from domain-bearing files. Expired cookies and unrelated domains are ignored. Local storage is not imported.

Direct Chrome reading is optional:

```sh
python -m luma_scraper whoami --chrome-profile 'you@example.com'
```

A directory name such as `Profile 1` or a unique profile display name also works. OS-protected cookie decryption is not guaranteed; use interactive login if it fails. Do not disable browser security to work around this.

## Servers and containers

Create the session on a desktop first, then transfer that file privately to the server under your control. Install the core package and run with `--session /private/path/session.json`. Treat that file like a password. Use private storage and directory permissions, not a public container image or repository.

A session is not an API key and may expire or be rejected in a different environment. This project does not promise unattended session renewal. Log in on a desktop again when required. CI never needs your session.

## Upgrading

From your clone with the virtual environment active:

```sh
git pull --ff-only
python -m pip install --upgrade '.[login]'
python -m luma_scraper --help
```

Read [the changelog](../CHANGELOG.md) for compatibility changes. For reproducibility, use a tagged GitHub release and pin its version rather than tracking the default branch.

## Storage

Sessions are excluded under `.sessions/`; outputs under `exports/`. Both can contain sensitive information. On POSIX systems new files use mode `0600`. On Windows, access follows directory ACLs. If you choose other directories, you are responsible for keeping them out of version control and shared folders.

Output and session files are not overwritten. Choose a new name for a refreshed session or rerun export. Delete old files yourself when no longer needed; deleting a local session file does not revoke the server-side login.
