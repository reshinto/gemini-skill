# Capabilities — Tools

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Commands that let Gemini call external tools and grounded data sources — function calling, sandboxed code execution, Google Search, and Maps grounding.

## Commands in this category

- `function_calling` → [function_calling.md](../reference/function_calling.md)
- `code_exec` → [code_exec.md](../reference/code_exec.md)
- `search` → [search.md](../reference/search.md)
- `maps` → [maps.md](../reference/maps.md)

---

### Function calling

**Status:** Stable

Model can call your defined functions/tools and receive responses.

**Capabilities:**
- Define custom functions with OpenAPI schema
- Multi-turn function calling (model calls, you respond, model calls again)
- Automatic tool state preservation

**Limitations:**
- You must implement function logic (skill only dispatches calls)
- Tool schema must be valid OpenAPI 3.0
- No asynchronous tool execution (request must complete)

**Use cases:**
- Calculator and math functions
- Web API integrations
- Database queries
- Real-time data retrieval

See [function_calling.md](../reference/function_calling.md).

### Code execution

**Status:** Stable

Execute Python code in Gemini's sandboxed environment.

**Capabilities:**
- Python 3.x standard library
- Fast code execution
- Access to stdout/stderr
- Math and data processing libraries

**Limitations:**
- Sandbox: no internet access, no external files
- Limited to standard library (no NumPy, Pandas, etc.)
- 30-second execution timeout
- State not preserved between calls

**Use cases:**
- Mathematical calculations
- Data manipulation and analysis
- Code verification
- Algorithm testing

See [code_exec.md](../reference/code_exec.md).

### Google Search grounding

**Status:** Stable (privacy-sensitive)

Ground responses in real-time Google Search results.

**Capabilities:**
- Live search integration
- Up-to-date information (within hours)
- Search source attribution

**Limitations:**
- Dispatcher auto-applies the internal privacy opt-in flag
- Slower than text-only (network latency)
- Adds cost per request
- May cite unreliable sources

**Use cases:**
- Current events and news
- Stock prices and market data
- Recent discoveries and research
- Up-to-date product information

See [search.md](../reference/search.md).

### Google Maps grounding

**Status:** Stable (privacy-sensitive)

Ground responses in Google Maps location data.

**Capabilities:**
- Real-time business and location data
- Map-aware responses
- Attribution required

**Limitations:**
- Dispatcher auto-applies the internal privacy opt-in flag
- Location queries may reveal intent
- Mandatory output schema enforced
- Adds cost per request
- Currently routed via the raw HTTP backend at runtime (SDK 1.33.0 does not expose this surface)

**Use cases:**
- Business finder (restaurants, stores)
- Location recommendations
- Route and navigation queries
- Local event discovery

See [maps.md](../reference/maps.md).

---

## See also

- [capabilities.md](capabilities.md) — category index
- [commands.md](commands.md) — command routing
- [reference/index.md](../reference/index.md) — per-command reference
