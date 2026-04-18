# Capabilities — Experimental

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Preview commands for emerging Gemini surfaces — computer use, deep research, and the streaming Live API.

## Commands in this category

- `computer_use` → [computer_use.md](../reference/computer_use.md)
- `deep_research` → [deep_research.md](../reference/deep_research.md)
- `live` → [live.md](../reference/live.md)

---

### Computer use

**Status:** Preview (v1beta, privacy-sensitive)

Enable the model to capture screenshots, analyze UI, and simulate keyboard/mouse input.

**Capabilities:**
- Screenshot capture
- UI element detection
- Keyboard and mouse input simulation
- Long-running tasks

**Limitations:**
- Preview feature (API may change)
- Can capture sensitive data on screen (privacy risk)
- Input simulation is best-effort
- High latency (multiple round-trips)
- Not suitable for sensitive environments
- Currently routed via the raw HTTP backend at runtime (SDK 1.33.0 does not expose this surface)

**Use cases:**
- Automate desktop tasks
- Navigate GUI applications
- Screenshot analysis
- Automated testing

**Caution:** Do not use with sensitive data visible (passwords, financial info, PII).

See [computer_use.md](../reference/computer_use.md).

### Deep Research

**Status:** Preview (Interactions API, privacy-sensitive)

Conduct multi-step research tasks with server-side storage and resumption.

**Capabilities:**
- Multi-step research (agent-like)
- Server-side result storage
- Session resumption (`--resume`)
- Background processing

**Limitations:**
- Preview feature (API may change)
- Asynchronous: long-running (30s–5min)
- Storage expires: 55 days (paid), 1 day (free)
- Requires `--execute` (mutating)
- High cost

**Use cases:**
- Thorough research investigation
- Multi-source synthesis
- Complex analysis tasks
- Background research

See [deep_research.md](../reference/deep_research.md).

> **Note:** The `live` command is listed in this category but has no capability description in the original source. See [live.md](../reference/live.md) for the reference entry.

---

## See also

- [capabilities.md](capabilities.md) — category index
- [commands.md](commands.md) — command routing
- [reference/index.md](../reference/index.md) — per-command reference
