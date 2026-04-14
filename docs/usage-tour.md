# Usage Tour

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

This guide walks through 16 common scenarios, each with a runnable command,
expected output, and explanation. All examples assume you've completed
[installation](install.md) and either let the installer write
`GEMINI_API_KEY` into `~/.claude/settings.json` or exported it manually for
local development.

---

## 1. First-Time Setup

See [Installation Guide](install.md) for the full setup flow. Quick summary:

After installation, verify with:

```bash
/gemini help
```

Expected output: List of all available commands.

The examples below use `python3 scripts/gemini_run.py ...` syntax because they
also double as repo-local development examples from a checkout.

---

## 2. One-Shot Text Generation

**Scenario:** Generate a quick response without starting a session.

```bash
python3 scripts/gemini_run.py text "Write a haiku about debugging code"
```

Expected output:

```
Semicolon lost,
Call stack tumbles downward,
Hope restored by print.
```

**Explanation:** The `text` command generates text from a prompt. No session is created; the context is forgotten after the response. Use `--session <id>` to save context for follow-ups.

---

## 3. Multi-Turn Session

**Scenario:** Have a back-and-forth conversation where the model remembers prior messages.

```bash
# Start a new session
python3 scripts/gemini_run.py text "I'm planning a trip to Japan" --session travel-2025

# Expected output: Travel planning suggestions

# Follow up (context includes the prior message)
python3 scripts/gemini_run.py text "Can you focus on food recommendations?" --session travel-2025

# Expected output: Suggestions for restaurants and local dishes,
# informed by the prior message about the Japan trip

# Or use --continue to reuse the most recent session
python3 scripts/gemini_run.py text "What about accommodations?" --continue
```

**Explanation:** `--session <id>` stores the conversation at `~/.claude/gemini-skill/sessions/<id>/` and includes all prior turns. `--continue` is shorthand for the most recent session.

---

## 4. Multimodal Analysis (PDF + Prompt)

**Scenario:** Ask the model to analyze a file (PDF, image, audio, video).

```bash
# Analyze a PDF
python3 scripts/gemini_run.py multimodal \
  "Summarize the key findings in this research paper" \
  --file /path/to/paper.pdf

# Expected output: Summary of the PDF's contents

# Or analyze an image
python3 scripts/gemini_run.py multimodal \
  "Describe what you see in this image" \
  --file /path/to/photo.jpg

# Include multiple files
python3 scripts/gemini_run.py multimodal \
  "Compare these two images" \
  --file /path/to/image1.jpg \
  --file /path/to/image2.jpg
```

**Explanation:** The `multimodal` command accepts text prompts + files. The model analyzes the files alongside your prompt and returns observations. Supported formats: PDF, images (JPEG, PNG, GIF, WebP), audio (MP3, WAV), and video (MP4, MOV).

---

## 5. Structured Output (JSON Schema)

**Scenario:** Extract structured data (JSON) that matches a schema you define.

```bash
# Extract a person's details into a JSON object
python3 scripts/gemini_run.py structured \
  "Extract name, age, and email from this text: John Doe, 28, john@example.com" \
  --schema '{
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "age": {"type": "integer"},
      "email": {"type": "string"}
    },
    "required": ["name", "age", "email"]
  }'

# Expected output:
# {
#   "name": "John Doe",
#   "age": 28,
#   "email": "john@example.com"
# }
```

**Explanation:** The `structured` command forces the model's response into a JSON schema you provide. Useful for data extraction, form filling, and automation where you need predictable, machine-readable output. Pass the schema via stdin or a file if it's complex.

---

## 6. Streaming Output

**Scenario:** See the model's response in real-time as it's generated, instead of waiting for the full response.

```bash
python3 scripts/gemini_run.py text \
  "Write a 5-paragraph essay on the history of AI" \
  --stream

# Expected output:
# Paragraph 1 printed in real-time as it's generated
# Paragraph 2 printed as it becomes available
# ...
# (All 5 paragraphs gradually appear)
```

**Explanation:** `--stream` shows output as it arrives instead of buffering the full response. Useful for long-running generation where you want immediate feedback. Incompatible with `--output` (streaming doesn't buffer to files).

---

## 7. Function Calling

**Scenario:** Ask the model to call predefined functions (tools) to accomplish a task.

```bash
# Define a function the model can call
python3 scripts/gemini_run.py function_calling \
  "What is the current weather in San Francisco? Use the get_weather tool." \
  --tool '{
    "name": "get_weather",
    "description": "Get the current weather for a city",
    "parameters": {
      "type": "object",
      "properties": {
        "city": {"type": "string"}
      },
      "required": ["city"]
    }
  }'

# Expected output:
# The model decides it needs to call get_weather("San Francisco")
# You implement the actual function; the model orchestrates it
# Output: "The weather in San Francisco is 72°F and sunny"
```

**Explanation:** Function calling lets the model decide to invoke functions you define. Useful for agent-like systems where the model drives actions (API calls, database queries, tool invocations). You provide the function definitions; the model decides when/how to call them.

---

## 8. Search Grounding

**Scenario:** Generate text using current web information (search grounding).

```bash
# Ask a question that requires current information
python3 scripts/gemini_run.py text \
  "What are the latest developments in quantum computing as of today?" \
  --search \
  --show-grounding

# Expected output:
# Generated response citing recent news
# [Grounding sources]
# - https://example.com/quantum-breakthrough (snippet)
# - https://example.com/quantum-update (snippet)
# ...
```

**Explanation:** `--search` enables web search grounding (the model searches the web and grounds its response in real results). `--show-grounding` displays the URLs and snippets that informed the response. Search grounding costs extra (typically 2x tokens); see `reference/search.md` for the economics.

---

## 9. Image Generation (Gemini-Native)

**Scenario:** Generate an image from a text description.

```bash
# Quick image generation (Gemini-native)
python3 scripts/gemini_run.py image_gen \
  "A cozy bookshop on a rainy evening, warm lighting" \
  --execute

# Expected output:
# Image saved to /tmp/gemini-image-<timestamp>.png
# Cost: $0.01
```

**Explanation:** `image_gen` generates images. By default, it uses the fastest Gemini-native model. Pass `--execute` to actually generate (dry-run mode is default). The skill saves large responses (images, videos) to a temp file and returns the path. Use `--output /path/to/image.png` to specify where to save.

---

## 10. Image Generation (Imagen)

**Scenario:** Generate a photorealistic image (Imagen backend).

```bash
# Generate with Imagen for photorealism
python3 scripts/gemini_run.py image_gen \
  "A professional headshot of a person smiling, studio lighting" \
  --model imagen-3.0-generate-002 \
  --execute

# Expected output:
# Image saved to /tmp/gemini-image-<timestamp>.png
# Cost: $0.05 (typically more expensive than Gemini-native)
```

**Explanation:** Imagen excels at photorealistic images. Trade-off: slower and costlier than Gemini-native generation. Use when you need production-quality, detailed imagery. The `--model` flag overrides the default model choice.

---

## 11. Video Generation

**Scenario:** Generate a short video from a text description.

```bash
# Generate a 5-second video (expensive; use sparingly)
python3 scripts/gemini_run.py video_gen \
  "A cat chasing a laser pointer across a hardwood floor, 5 seconds" \
  --execute

# Expected output:
# Video saved to /tmp/gemini-video-<timestamp>.mp4
# Cost: $0.50 (expensive; verify the cost in dry-run mode)
```

**Explanation:** `video_gen` generates short videos. This is an expensive operation; always check the cost in dry-run mode first (omit `--execute` to see the cost without generating). The video is saved to a file; use `--output` to specify the location.

---

## 12. Batch Processing

**Scenario:** Process multiple requests in a single batch (50% cost savings).

```bash
# Create a JSONL file with requests (one per line)
cat > /tmp/batch-requests.jsonl << 'EOF'
{"prompt": "Translate 'hello' to French"}
{"prompt": "Translate 'goodbye' to French"}
{"prompt": "Translate 'thank you' to French"}
EOF

# Submit the batch
python3 scripts/gemini_run.py batch \
  --file /tmp/batch-requests.jsonl \
  --execute

# Expected output (after ~30 seconds):
# Batch job ID: batch-<id>
# Status: processing
# Check status with: gemini batch --status batch-<id>
```

**Explanation:** Batch processing is async and cheaper (typically 50% of the cost). Submit a JSONL file with multiple requests; the API processes them in the background. Use `--status <batch-id>` to check progress. Ideal for bulk processing, but introduces latency (results available after ~30s to minutes).

---

## 13. Context Caching

**Scenario:** Reuse a large prompt (or file) multiple times to save cost.

```bash
# First request (cache is created; higher latency)
python3 scripts/gemini_run.py multimodal \
  "Summarize the key metrics from this report" \
  --file /path/to/large-report.pdf \
  --cache

# Expected output: Summary (with caching overhead)

# Second request reusing the same file (cache hits; lower cost)
python3 scripts/gemini_run.py multimodal \
  "Extract all mentioned growth percentages from the report" \
  --file /path/to/large-report.pdf \
  --cache

# Cost: ~60% cheaper than the first request due to cache hit
```

**Explanation:** Context caching stores parts of your request (files, large prompts) and reuses them for subsequent requests. The first request adds caching latency; subsequent requests are faster and cheaper (cached tokens cost ~25% of regular tokens). Worth it for large prompts reused 3+ times.

---

## 14. File Upload and Reference

**Scenario:** Upload a file and reference it in a later request.

```bash
# Upload a file
python3 scripts/gemini_run.py file upload /path/to/document.pdf

# Expected output:
# File ID: file-abc123def456
# File uploaded: document.pdf (2.3 MB)
# Valid for: 48 hours

# Reference the file in a later request
python3 scripts/gemini_run.py text \
  "Analyze the document I uploaded earlier" \
  --file-id file-abc123def456

# Cost: Cheaper than re-uploading the file each time
```

**Explanation:** File upload stores files on the Gemini API server. Reference them by ID in later requests without re-uploading. Saves bandwidth and cost for large files used multiple times. Files expire after 48 hours; re-upload if needed.

---

## 15. Cost Tracking & Interpretation

**Scenario:** Understand how much quota your commands consume.

```bash
# Run a command with cost breakdown
python3 scripts/gemini_run.py text \
  "Write a 500-word essay on machine learning" \
  --cost-breakdown

# Expected output:
# Generated essay...
#
# Cost Breakdown:
# Input tokens: 15 @ $0.15/1M = $0.0000023
# Output tokens: 487 @ $0.60/1M = $0.0002922
# Total: $0.0002945

# Common cost interpretations:
# - Text generation with Flash: <$0.001 per request
# - Multimodal (image) with Flash: $0.01-$0.05 per request
# - Video generation: $0.20-$1.00 per video
# - Pro model: 10x more expensive than Flash per token
# - Batch processing: 50% cheaper than regular processing
```

**Explanation:** `--cost-breakdown` shows exactly how many tokens you used and the cost in USD. Use this to budget your usage and understand which operations are expensive. The skill also prints estimated costs in dry-run mode before executing.

---

## 16. Dry-Run vs Execute Discipline

**Scenario:** Validate a command before actually running it.

```bash
# Dry-run: see what would happen without executing
python3 scripts/gemini_run.py image_gen \
  "A space station orbiting Earth" \
  # (no --execute flag)

# Expected output:
# [DRY RUN] Would execute image_gen:
# Model: gemini-3.1-flash-image-preview
# Backend: SDK (primary)
# Estimated tokens: 25 input + 0 output
# Estimated cost: $0.00003
# Resolution: 1024x1024
#
# To actually generate, run:
# python3 scripts/gemini_run.py image_gen "A space station..." --execute

# Once you're confident, add --execute
python3 scripts/gemini_run.py image_gen \
  "A space station orbiting Earth" \
  --execute

# Expected output:
# Image saved to /tmp/gemini-image-<timestamp>.png
# Actual cost: $0.00003
```

**Explanation:** All mutation commands (image_gen, video_gen, batch, etc.) default to dry-run mode. This lets you validate syntax, flags, and cost before committing quota. Use `--execute` (or `-x`) to actually run the command. This discipline prevents accidental expensive operations.

---

## Common Patterns

### Iterating on a Prompt

```bash
# Start a session
python3 scripts/gemini_run.py text "Initial idea" --session work-session

# Refine iteratively
python3 scripts/gemini_run.py text "Make it shorter" --continue
python3 scripts/gemini_run.py text "Add more examples" --continue
```

### Extracting Data from Files

```bash
# Extract structured data from a PDF
python3 scripts/gemini_run.py structured \
  "Extract all invoice numbers and amounts" \
  --file /path/to/invoices.pdf \
  --schema '{
    "type": "object",
    "properties": {
      "invoices": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "invoice_number": {"type": "string"},
            "amount": {"type": "number"}
          }
        }
      }
    }
  }'
```

### Batch Analysis with Session Context

```bash
# Set up context in a session
python3 scripts/gemini_run.py text \
  "You are a code reviewer. Be strict and specific." \
  --session code-review

# Analyze multiple files in sequence
for file in /path/to/code/*.py; do
  echo "Reviewing $file..."
  python3 scripts/gemini_run.py text \
    "Review this code file" \
    --file "$file" \
    --continue
done
```

### Cost-Conscious Workflow

```bash
# Use Flash for quick iterations
python3 scripts/gemini_run.py text "draft the essay" --model gemini-2.5-flash

# Switch to Pro only for final refinement
python3 scripts/gemini_run.py text "polish for publication" --model gemini-2.5-pro

# Use Flash Lite for high-volume work
python3 scripts/gemini_run.py batch \
  --file /path/to/1000-items.jsonl \
  --model gemini-2.5-flash-lite \
  --execute
```

---

## Troubleshooting Common Errors

See `reference/troubleshooting.md` for detailed error handling and recovery steps.

Quick reference:

- **"API key not found"**: Run `python3 ~/.claude/skills/gemini/scripts/health_check.py` or check `~/.claude/settings.json`
- **"Backend unavailable"**: Check `GEMINI_IS_SDK_PRIORITY` / `GEMINI_IS_RAWHTTP_PRIORITY` in `~/.claude/settings.json`
- **"Timeout"**: Increase with `--timeout 60` or check network connectivity
- **"Rate limit exceeded"**: Reduce request frequency or use batch processing (cheaper)
- **"File too large"**: Use `--no-cache` or split into multiple requests

---

## Next Steps

- **Set up sessions:** Use `--session <id>` for multi-turn conversations
- **Optimize costs:** Use `--cost-breakdown` to understand your usage patterns
- **Explore advanced features:** See `reference/index.md` for all available commands
- **Read design patterns:** `docs/design-patterns.md` explains why the skill works the way it does

---

## Navigation

- **Previous:** [Models Reference](models-reference.md)
- **Next:** [Architecture](architecture.md)
