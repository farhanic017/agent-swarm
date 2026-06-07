# Security Policy

Agent Swarm can interact with files, terminals, browser tools, model providers, and local configuration. Please report security issues privately instead of opening a public issue.

## Reporting a Vulnerability

Email or contact the maintainer through the public GitHub profile:

https://github.com/farhanic017

Include:

- A short description of the issue.
- Steps to reproduce.
- Impact and affected versions or commits, if known.
- Any proof of concept that avoids exposing real secrets.

## Scope

Security reports are especially useful for:

- Credential exposure.
- Unsafe file access.
- Prompt-injection paths that can trigger dangerous tool use.
- Provider configuration leaks.
- Browser or terminal tool escape paths.
- Dependency vulnerabilities that affect the default install.

## Safe Defaults

Never commit `.env` files, API keys, private state, logs with secrets, browser cookies, SSH keys, cloud credentials, or personal provider configuration.
