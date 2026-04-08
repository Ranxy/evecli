---
name: evecli
description: Manage EVE Online in-game mail via the ESI CLI. Use when the user wants to read, send, delete, list, or update mail, manage mail labels, or check mailing lists in EVE Online.
disable-model-invocation: true
---

## EVE Game Management Skill

This skill uses the `evecli` CLI (Python-based) to interact with the EVE Online ESI API. All commands output JSON by default, making it easy to parse and present information.

### Prerequisites

- The user must be authenticated first: `evecli auth login`
- Check status: `evecli auth status`

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
```
- `--to` can be specified multiple times for multiple recipients
- `--body` supports HTML
- Returns: `{"status": "sent", "mail_id": "<id>"}`

#### Delete mail(s)
```
evecli mail delete <mail_id> [<mail_id>...]
```

#### Update mail
```
evecli mail update <mail_id> [--read|--unread] [--label <label_id>]
```

#### Manage labels
```
evecli mail label --action list
evecli mail label --action create --name <label_name> [--color "#hexcolor"]
evecli mail label --action delete --label-id <id>
```

### Common Workflows

#### Check recent unread mails
Run `evecli mail list --limit 30` and filter results showing `read: false` entries.

#### Read specific mail
After listing, if user asks to read mail N, use `evecli mail read <mail_id>`.

#### Send reply
Use `evecli mail send --to <char_id> --subject "RE: <original_subject>" --body <body>`.

#### Clean up old mails
Use `evecli mail delete <mail_id>` after confirming with the user.
