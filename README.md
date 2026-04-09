# evecli

A CLI backend for LLM assistants to manage [EVE Online](https://www.eveonline.com/) game data via the ESI API.
This is a completely vibe coding project, please use with caution.

## Purpose

`evecli` is designed to be used by AI coding assistants (Claude Code, etc.) as a tool skill. Rather than having the LLM call ESI API endpoints directly, it dispatches structured CLI commands through a skill definition. This provides:

- **Safe abstraction** — the skill document (`.claude/skills/*/SKILL.md`) tells the LLM exactly what it can and can't do
- **Consistent JSON output** — all commands return machine-parseable JSON by default, making it easy for the LLM to present results to the user
- **Built-in auth** — OAuth2 SSO with automatic token refresh, transparent to the LLM

The human user interacts with the LLM in natural language, and the LLM translates those requests into `evecli` commands.

## Architecture

```
User (natural language)
  ↓
LLM assistant (Claude Code + skills)
  ↓
skill definition (.claude/skills/eve-mail/SKILL.md)
  ↓
evecli CLI commands
  ↓
EVE Online ESI API
```

## Installation

```bash
python -m pip install evecli-llm
```

For local development:

```bash
pip install -e .
```

## Quick Start

### 1. Create an EVE Online Application

1. Log in to the [EVE Online Developer Portal](https://developers.eveonline.com/)
2. Create a new application with a callback URL of `http://localhost:6480/callback`
3. Copy the **Client ID** and **Secret Key**

### 2. Authenticate

```bash
evecli auth login --client-id <client-id> --secret <secret-key>
```

This opens a browser for EVE Online OAuth2 authorization. Tokens are stored at `~/.config/evecli/tokens.json` and refreshed automatically.

### 3. Let Your LLM Assist Manage EVE

Once authenticated, ask your LLM assistant to help with EVE tasks:

- _"Check my recent unread mails"_
- _"Read mail #12345 and summarize it"_
- _"Send a mail to character 90123456 with subject 'Hello' and body '...'"_
- _"Delete all mails older than list item #5"_

The LLM will use the `eve-mail` skill to execute the appropriate `evecli` commands and present results back to you.

## Commands

| Command | Description |
|---------|-------------|
| `evecli auth login` | Authenticate via EVE SSO OAuth2 |
| `evecli auth status` | Show auth status and token expiry |
| `evecli auth logout` | Remove stored tokens |
| `evecli auth character` | Show authenticated character info |
| `evecli mail list` | List recent mails |
| `evecli mail read <id>` | Read a single mail |
| `evecli mail send` | Send a new mail (body supports HTML) |
| `evecli mail delete <ids>` | Delete mail(s) |
| `evecli mail label` | Manage mail labels (list/create/delete) |
| `evecli mail update <id>` | Update read status or labels |

All commands support `--format json` (default) and `--format plain`.

## Skills

Skills are defined in `.claude/skills/*/SKILL.md` and loaded by Claude Code automatically. The skill document tells the LLM:

- What capabilities are available
- Exact command syntax and parameters
- Common workflows (check unread, reply to mail, etc.)
- Expected output format for parsing

To add new capabilities, create a new skill directory under `.claude/skills/` with a `SKILL.md` following the same pattern.

## Tech Stack

- **Click** — CLI framework
- **httpx** — HTTP client for ESI API requests
- **Pydantic** — Data validation

## License

MIT
