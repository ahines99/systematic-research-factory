# ADR-0004: API-key authentication for v1; hosted OAuth only for a Claude.ai connector

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-062, RSF-063, RSF-079, RSF-083

## Context
The deployed MCP server needs authentication. The MCP authorization spec is built on OAuth. Implementing it in full means running an authorization server with login, client registration and PKCE. That is a lot of security-sensitive code, and none of it demonstrates research governance.

The clients that matter for v1 (Claude Code, the Agent SDK, and scripts) can send custom HTTP headers. At the time of writing, Claude.ai custom connectors support OAuth or no authentication, but not static API keys; verify this before starting RSF-083.

## Decision
1. **v1 uses bearer API keys** (RSF-062).
   - Keys are random, high-entropy, shown once, and stored only as hashes.
   - Each key belongs to one role (`researcher`, `approver` or `viewer`, RSF-063) and can be revoked.
   - Keys are issued through the CLI.
2. **Roles are enforced on the server.** Only approvers write approval records, and a committee approver cannot be the run's requester.
3. **The public demo has a read-only guest role that needs no login** (RSF-079). Guests browse pre-recorded runs (RSF-082) and are rate-limited.
4. **If a Claude.ai connector is wanted, use a hosted identity provider** (RSF-083, optional). The server only validates the provider's tokens; we never build an authorization server.

## Alternatives considered
- **Full OAuth from v1:** rejected because of its cost and security surface. Nothing in v1 requires it.
- **No authentication behind a private network:** rejected because the public demo needs role separation, and approvals must be attributable to an identity.

## Consequences
- The authentication code is small and reviewable.
- Approval records carry the key's owner as the approver identity.
- Adding Claude.ai as a client later is additive: it adds a token validator, not a rewrite.

## Revisit when
More than a handful of human users need access, single sign-on is required, or Claude.ai connector access becomes a goal.
