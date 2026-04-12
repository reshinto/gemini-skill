# Security

**Last Updated:** 2026-04-13

Threat model, authentication, data protection, and risk management.

## Threat Model

### Assets

- **API key** — grants access to Gemini API (cost control, data processing)
- **User data** — prompts, files, conversation history (sensitivity varies)
- **Generated files** — images, videos, music, large responses (locally stored)
- **Session data** — multi-turn conversation history (locally stored)

### Threats

#### 1. API Key Leakage

**Risk:** Attacker gains API key → can use your quota, incur costs, access account.

**Mitigations:**
- **Exclusive HTTP header auth:** API key never in URL query strings
  ```
  Header: x-goog-api-key: <key>
  NOT: https://api.example.com?key=<key>
  ```
- **Shell env precedence:** `GEMINI_API_KEY` env var takes priority over `.env`
  ```bash
  export GEMINI_API_KEY="..."  # ← This always wins
  # ~/.claude/skills/gemini/.env is read only if env var not set
  ```
- **File permissions:** `.env` file should be mode `600` (readable only by owner)
  ```bash
  chmod 600 ~/.claude/skills/gemini/.env
  ```
- **No logging:** API key is **never logged**, printed, or stored in response files
- **No git:** `.env` is in `.gitignore`; never commit keys to version control

**Assumptions:**
- Your shell environment is not compromised
- File system permissions are enforced by your OS
- You don't run untrusted code as your user

#### 2. Prompt Injection

**Risk:** Attacker crafts a prompt that tricks the model into revealing system instructions or ignoring user intent.

**Mitigation:**
- **User input isolation:** All user input passed as opaque string arguments, never shell-interpolated
  ```bash
  # SAFE: User input passed as single argv value
  /gemini text "user input here"
  
  # UNSAFE (not used): Shell concatenation
  /gemini text $user_input  # ← DO NOT DO
  ```
- **No `allowed-tools` pre-approval in the skill manifest:** earlier versions of `SKILL.md` declared a Claude Code `allowed-tools: Bash(python3 ...)` line to pre-approve the launcher script. That field is valid in slash commands (`.claude/commands/*.md`) but **not** in skills (`.claude/skills/*/SKILL.md`) — its presence caused the Claude Code skill loader to silently reject the manifest. It has been removed. Bash invocations of `scripts/gemini_run.py` now follow the user's normal Claude Code tool-permission flow, which is the correct behavior: policy belongs in the dispatcher and the user's permission settings, not in the skill manifest.

**Assumptions:**
- You trust Claude Code's model integrity
- You review custom system instructions

#### 3. Large Response / Token Overflow

**Risk:** API returns huge response (50KB+) → token overhead in Claude Code, expensive to reprocess.

**Mitigation:**
- **Large response guard (50KB threshold):**
  ```python
  if len(response_text) > 50_000:
      output_path = /tmp/response_xyz.txt
      save_to_file(output_path)
      print(f"[Response saved to {output_path}]")
  else:
      print(response_text)
  ```
- **Media always to file:** Images, videos, music never output raw (always file paths)
- **User can download:** Claude Code can read returned file paths

**Assumptions:**
- File system is secure (temp dir not world-readable)
- Claude Code can be trusted with file paths

#### 4. Concurrent Access / Race Conditions

**Risk:** Claude Code parallelizes tool calls → two skill invocations access state simultaneously → data corruption.

**Mitigation:**
- **File locking + atomic writes:**
  ```python
  # POSIX: fcntl.flock()
  with open(state_file, 'r+') as f:
      fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
      state = json.load(f)
      state['cost'] += delta
      f.seek(0)
      json.dump(state, f)
      f.truncate()
  
  # Windows: msvcrt.locking()
  ```
- **Atomic swaps:** Use `os.replace()` to atomically swap files
- **Retry logic:** Windows retry loop (antivirus scanner may hold lock)

**Assumptions:**
- `fcntl.flock()` works on your file system (some NFS mounts don't support it)
- `os.replace()` is atomic on your OS (POSIX and Windows both support it)

#### 5. Unencrypted Local Storage

**Risk:** Conversation history, session data, file state stored in plaintext → attacker reads from disk.

**Mitigation:**
- **No encryption** (stdlib only, no deps) — rely on OS-level security
  ```bash
  # Session history stored as JSON (plaintext)
  ~/.config/gemini-skill/sessions/<id>.json
  
  # Owner should restrict permissions
  chmod 700 ~/.config/gemini-skill/
  ```
- **User responsibility:** Encrypt `~/.config/` at OS level (BitLocker, FileVault, etc.)

**Assumptions:**
- Your OS enforces file permissions
- You own the machine or have OS-level encryption

#### 6. Privacy-Sensitive Operations (Search, Maps, Computer Use)

**Risk:** Sending queries to third-party services (Google Search, Google Maps) reveals user intent.

**Mitigations:**
- **Explicit opt-in (no silent sending):**
  ```bash
  # SAFE: Explicitly use /gemini search
  /gemini search "covid-19 latest updates"
  
  # NOT: Automatic search for every query
  # The skill does not auto-enable search for ambiguous queries
  ```
- **Clear documentation:** `reference/search.md`, `reference/maps.md`, `reference/computer_use.md` explain privacy implications
- **Policies in SKILL.md:** Comments warn about privacy-sensitive commands
- **No automatic profiling:** Skill does not profile user behavior or preferences

**Assumptions:**
- Users read docs before using privacy-sensitive commands
- Google respects privacy commitments (verify independently)

#### 7. Dependency Vulnerability (None at Runtime)

**Risk:** Third-party package has a security vulnerability.

**Mitigation:**
- **Stdlib only:** No runtime dependencies
  - No `requests`, no `pyyaml`, no `lxml`, etc.
  - Eliminates entire class of supply-chain attacks
  - Trades for reinventing wheels (urllib instead of requests, JSON instead of YAML)

**Assumptions:**
- Python standard library is trustworthy
- Your Python installation is not compromised

#### 8. Model Outputs (Hallucinations, Bias, Toxicity)

**Risk:** Model generates harmful, biased, or incorrect content.

**Mitigation:**
- **No output filtering** — this is a "thin" skill that doesn't filter model outputs
- **User responsibility:** Review model outputs before using
- **Transparency:** Skill does not claim to be safe; docs explain limitations

**Assumptions:**
- Users understand LLM limitations (hallucinations, bias, toxicity)
- Users review outputs before relying on them for high-stakes decisions

---

## Authentication

### API Key Resolution

The skill uses an **ordered lookup chain**:

1. **Shell environment variable:** `GOOGLE_API_KEY` or `GEMINI_API_KEY`
2. **`.env` file:** `~/.claude/skills/gemini/.env`
3. **Error:** If neither found

```python
def resolve_key():
    # First: shell env var (always wins)
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    
    # Second: .env file
    env_path = Path.home() / ".claude" / "skills" / "gemini" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    
    # Error: no key found
    raise AuthError("API key not found. Set GEMINI_API_KEY env var or .env file.")
```

### HTTP Authentication

All requests use the **`x-goog-api-key` HTTP header**:

```python
request.add_header("x-goog-api-key", api_key)
```

**Never in URL query string:**
```python
# SAFE: header auth
url = "https://generativelanguage.googleapis.com/v1beta/models/..."
headers["x-goog-api-key"] = key

# UNSAFE: query auth (NOT USED)
# url = f"https://...?key={key}"  ← NEVER
```

Query string auth risks:
- Browser history logs
- Proxy/ISP logs
- Referrer headers
- Access logs

---

## Data Protection

### Sensitive Data

**Inputs:**
- Prompts (user queries)
- Uploaded files (PDFs, images, etc.)
- System instructions
- Session conversation history

**Outputs:**
- Model responses
- Generated images/videos/music
- Embeddings
- Analysis results

### Data In Transit

- **HTTPS only:** All API calls use HTTPS (encrypted in flight)
- **No logging:** API key and response bodies are not logged
- **Timeouts:** All requests have explicit timeouts (prevent hanging connections)

### Data At Rest

- **Session history:** Stored in `~/.config/gemini-skill/sessions/<id>.json` (user-readable JSON, no encryption)
- **File state:** `~/.config/gemini-skill/files.json` (no encryption)
- **Cost tracking:** `~/.config/gemini-skill/cost_today.json` (no encryption)
- **Generated files:** Saved to OS temp dir or user-specified output dir (no encryption)

**User responsibility:**
- Encrypt `~/.config/` at OS level (BitLocker, FileVault, etc.)
- Restrict output directory permissions
- Delete sensitive files after use

### Data Deletion

- **Session delete:** `rm ~/.config/gemini-skill/sessions/<id>.json`
- **All sessions delete:** `rm -rf ~/.config/gemini-skill/sessions/`
- **Skill uninstall:** `rm -rf ~/.claude/skills/gemini/`
- **Server-side files:** Use `/gemini files delete <file_id> --execute` to remove from Gemini API
- **Conversational history:** Not deleted automatically; your responsibility

---

## Sanitization

### Input Validation

- **Command whitelist:** Only commands in `ALLOWED_COMMANDS` are runnable
- **Argument parsing:** Each adapter validates its own arguments
- **File paths:** Local file paths are checked to exist before upload
- **URLs:** Not supported in multimodal (file paths only)

### Output Sanitization

- **Safe print:** All stdout uses `safe_print()` to prevent ANSI injection
  ```python
  def safe_print(text: str) -> None:
      """Remove ANSI escape sequences before printing."""
      text = re.sub(r'\x1b\[[0-9;]*m', '', text)  # Strip ANSI codes
      print(text)
  ```
- **No HTML/Markdown rendering:** Responses are plain text (Claude Code handles rendering)

### Integrity Checking

- **No checksums:** Installed files are **not** integrity-checked (TODO: could add)
- **Risk:** Attacker modifies installed files (requires write access to `~/.claude/`)
- **Mitigation:** Restrict permissions on `~/.claude/` directory

---

## API Key Best Practices

1. **Use environment variable:**
   ```bash
   export GEMINI_API_KEY="sk-..."  # Shell profile
   ```

2. **Restrict `.env` permissions:**
   ```bash
   chmod 600 ~/.claude/skills/gemini/.env
   ```

3. **Rotate keys regularly** (via Google Cloud Console):
   - Delete old keys
   - Create new keys
   - Update shell profile or `.env`

4. **Use quota limits** (via Google Cloud Console):
   - Set daily/monthly budget limits
   - Alerts for unusual usage

5. **Never commit keys:**
   ```bash
   # SAFE: .env in .gitignore
   # UNSAFE: keys in code comments or git history
   ```

6. **Don't share keys:**
   - Each user should have their own key
   - Each project should have its own key
   - If compromised, revoke immediately

---

## Reporting Security Issues

If you find a security vulnerability:

1. **Do not file a public issue**
2. **Email security contact** (check `SECURITY.md` in repo)
3. **Include proof-of-concept and steps to reproduce**
4. **Allow 90 days for patch before public disclosure**

---

## Compliance & Standards

- **No HIPAA:** Not suitable for healthcare data
- **No PCI-DSS:** Not suitable for payment card data
- **No SOC 2:** Not audited for compliance
- **GDPR consideration:** User data may be sent to Gemini API servers; verify with Google's data processing agreements

See https://ai.google.dev/terms for API terms of service.

---

## Summary

| Threat | Mitigation | Assumption |
|--------|-----------|-----------|
| API key leakage | Header auth, env precedence, no logging | Shell env secure |
| Prompt injection | Opaque string args, no shell interp | Claude Code trustworthy |
| Token overflow | 50KB guard, media to file | Temp dir secure |
| Concurrent access | File locking + atomic writes | fcntl/msvcrt work on your FS |
| Unencrypted storage | No crypto (stdlib only), file perms | OS enforces permissions |
| Privacy leak (search/maps) | Explicit opt-in, documentation | Users read docs |
| Dependency vuln | Stdlib only, no deps | Python stdlib trustworthy |
| Model outputs | No filtering, user review | Users understand LLM limits |

---

## Next steps

- **Installation:** [Install guide](install.md) (includes `.env` setup)
- **Privacy:** [Commands guide](commands.md) (search/maps/computer_use marked)
- **Architecture:** [System design](architecture.md) (auth, state management)
