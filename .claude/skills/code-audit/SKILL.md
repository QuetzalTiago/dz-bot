---
name: code-audit
description: Sweep the whole codebase (not just the current diff) for correctness bugs, security issues, concurrency/resource problems, hardcoded/duplicated values, and inconsistencies between sibling modules, using a two-pass sweep-then-verify method. Use when asked to audit, scan, or review the whole codebase/repo for bugs and quality issues, on a schedule or on demand — as opposed to /code-review, which reviews only the current diff.
---

Audit this codebase for defects and quality issues. Do it in two passes, not one skim.

## Pass 1 — sweep by category, across the whole codebase

Cover every category below across the full repo (excluding `.venv`, `node_modules`, build artifacts, and other vendored/dependency code) — do not restrict to recently touched files:

- **Correctness**: logic errors, off-by-one, wrong operator/condition, mishandled edge cases (empty/None/zero/negative/unicode), incorrect assumptions about external data shape.
- **Error handling & resources**: unhandled exceptions, bare/overbroad `except`, swallowed errors that should surface, unclosed sessions/files/connections, tasks/loops that die silently on first exception.
- **Concurrency & state**: shared mutable state without locking, blocking calls inside async code, race conditions, state that leaks between requests/users/guilds/sessions.
- **Security**: injection (SQL/command/template), secrets in code or logs, missing authz/ownership checks on privileged actions, SSRF via user-controlled URLs, unsafe deserialization, path traversal.
- **Duplication & hardcoded values**: the same literal (URL, host, magic number, timeout, limit, credential name) defined in more than one place instead of one named constant. A value duplicated *without* matching the exact shape you first noticed it in (missing scheme, different quoting, embedded in a header/path instead of a full URL) is still a duplicate — grep for the raw value, not just the pattern you expect it to appear in.
- **Contract consistency**: functions/modules that do the same job (e.g. sibling cogs/handlers/routes implementing the same kind of feature) but disagree on error messages, return shapes, retry/cooldown behavior, or logging — divergence there is usually an unintentional bug in one of them, not a deliberate design choice.
- **Dead code**: unreachable branches, unused params/returns, leftover flags or shims from a finished migration.
- **Test coverage**: behaviors with no test, tests that assert on mocks instead of real failure modes.

## Pass 2 — verify, don't just list

- For every candidate finding, state the concrete input/state that triggers it and the wrong outcome. "This looks off" is not a finding.
- When one file has a bug, check its siblings — files clearly copy-pasted from it, or implementing the same interface — for the same bug. Copy-paste propagates defects, and stopping at the first instance found is how the rest get missed.
- For hardcoded/duplicated values specifically: once you've identified the canonical value, grep the raw literal across the repo to confirm no other copy of it survives under a different name or in a different shape (header, path segment, comparison string).
- Distinguish "will misbehave" (confirmed — you traced the exact failure) from "looks suspicious but unverified" (plausible) and label accordingly.

## Scope and output

Exclude test fixtures/mocks unless the test itself is the defect. Report findings ranked most severe first via the ReportFindings tool if available; otherwise as a plain list of `file:line`, category, and the concrete failure scenario. Do not fix anything unless explicitly asked to — report first.
