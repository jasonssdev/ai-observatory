# Security policy

## Supported versions

AI Observatory is pre-1.0. Only the latest code on `main` receives security fixes.

## Reporting a vulnerability

Please do **not** open a public issue for security vulnerabilities.

Report them privately via [GitHub Security Advisories](https://github.com/jasonssdev/ai-observatory/security/advisories/new) or by email to jasonssdev@gmail.com. Include a description of the issue, steps to reproduce, and the potential impact.

You can expect an acknowledgement within a few days. Please allow reasonable time for a fix before any public disclosure.

## Scope notes

AI Observatory is local-first: it fetches public feeds/APIs and writes to a local SQLite database and Markdown files. Areas of particular interest are the parsing of untrusted feed/API content and anything that could cause data to leave the machine unintentionally.
