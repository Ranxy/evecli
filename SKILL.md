---
name: evecli
description: Install, set up, authenticate, and use the evecli ESI CLI for EVE Online mail tasks. Use when the user wants to bootstrap this project, verify the CLI is installed, log in with EVE SSO, read, send, delete, list, or update mail, manage mail labels, or send mail to a mailing list.
disable-model-invocation: true
---

## EVE Game Management Skill

This skill uses the `evecli` CLI (Python-based) to interact with the EVE Online ESI API. All commands output JSON by default, making it easy to parse and present information.

### Agent Bootstrap

Before using any mail command, make sure the CLI is installed and callable.

1. Check whether the CLI already exists:
```bash
command -v evecli
```

2. If `evecli` is missing and you are inside this repository root (the directory that contains `pyproject.toml`), install the project in editable mode:
```bash
python -m pip install -e .
```

3. If `evecli` is missing and you are not in the repository root, install the published package:
```bash
python -m pip install evecli-llm
```

4. Verify installation:
```bash
evecli --version
```

Prefer `python -m pip ...` over bare `pip ...` so the install targets the active Python environment.

If the CLI is present but commands fail because dependencies are stale, reinstall with:
```bash
python -m pip install -e .
```

### Prerequisites

- Check auth status first: `evecli auth status`
- If not authenticated, run: `evecli auth login --client-id <client-id> --secret <secret-key>`
- If the user has not provided credentials yet, ask for the EVE application `client-id` and `secret`
- Confirm the active character when needed: `evecli auth character`

### Recommended Execution Order

For a fresh environment, follow this sequence:

1. Install or verify `evecli`
2. Run `evecli auth status`
3. If needed, run `evecli auth login --client-id <client-id> --secret <secret-key>`
4. Optionally run `evecli auth character` to confirm the correct character
5. Execute the requested mail command

### Commands Reference

#### List mails
```
evecli mail list [--limit N] [--offset N] [--format json|plain]
```
- Default limit: 50
- Returns array of objects with: `mail_id`, `subject`, `from`, `timestamp`, `read`, `labels`

#### Read a mail
```
evecli mail read <mail_id> [--format json|plain]
```
- Returns: `mail_id`, `subject`, `body`, `from`, `recipients`, `timestamp`, `read`, `labels`
- The body field may contain HTML

#### Send a mail
```
evecli mail send --to <char_id> --subject <subject> --body <body> [--format json|plain]
evecli mail send --mailing-list <list_id> --subject <subject> --body <body> [--format json|plain]
```
- `--to` can be specified multiple times for multiple recipients
- `--mailing-list` sends to a mailing list instead of character recipients
- `--body` supports HTML
- Returns: `{"status": "sent", "mail_id": "<id>"}`

#### Delete mail(s)
```
evecli mail delete <mail_id> [<mail_id>...] [--format json|plain]
```

#### Update mail
```
evecli mail update <mail_id> [--read|--unread] [--label <label_id>] [--format json|plain]
```

#### Manage labels
```
evecli mail label --action list
evecli mail label --action create --name <label_name> [--color "#hexcolor"]
evecli mail label --action delete --label-id <id>
```

### Execution Rules

- Prefer JSON output unless the user explicitly asks for plain text
- Run `evecli auth status` before assuming the session is usable
- Do not claim mailing list inspection support; this CLI only supports sending to a mailing list via `--mailing-list`
- If a command returns an authentication error, guide the user through login again instead of retrying mail commands blindly
- When deleting mails in bulk, confirm destructive intent if the user did not state it clearly

### Common Workflows

#### Check recent unread mails
Run `evecli mail list --limit 30` and filter results showing `read: false` entries.

#### Read specific mail
After listing, if user asks to read mail N, use `evecli mail read <mail_id>`.

#### Send reply
Use `evecli mail send --to <char_id> --subject "RE: <original_subject>" --body <body>`.

#### Clean up old mails
Use `evecli mail delete <mail_id>` after confirming with the user.

#### First-time setup for the user

1. Install `evecli`
2. Run `evecli auth login --client-id <client-id> --secret <secret-key>`
3. Verify with `evecli auth status`
4. Start with `evecli mail list --limit 20`
