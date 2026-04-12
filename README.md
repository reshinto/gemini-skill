# gemini-skill

A Claude Code skill for broad Gemini REST API access — text generation, multimodal input, image/video/music generation, embeddings, caching, batch processing, search grounding, code execution, file search, and more.

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/reshinto/gemini-skill.git
   cd gemini-skill
   ```

2. **Set your Gemini API key** (get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))
   ```bash
   export GEMINI_API_KEY=your_key_here
   ```
   Or edit the `.env` file created during install.

3. **Install the skill**
   ```bash
   python3 setup/install.py
   ```

4. **Use it in Claude Code**
   ```
   /gemini text "Explain quantum computing"
   ```

## Features

- Text generation, multimodal input, structured output, function calling
- Image generation (Nano Banana family), video generation (Veo), music generation (Lyria 3)
- Embeddings, context caching, batch processing, token counting
- Google Search grounding, Google Maps grounding, code execution
- File API, File Search / hosted RAG
- Deep Research (Interactions API), Computer Use (preview)
- Automatic model routing by task type and complexity
- Two-phase cost tracking (pre-flight estimate + post-response)
- Multi-turn conversation sessions with Gemini
- Zero runtime dependencies — Python 3.9+ stdlib only

## Prerequisites

- Python 3.9+
- A Gemini API key

## Documentation

See [docs/](docs/) for full documentation including:
- [Architecture](docs/architecture.md)
- [How It Works](docs/how-it-works.md)
- [Installation](docs/install.md)
- [Commands](docs/commands.md)
- [Capabilities](docs/capabilities.md)
- [Security](docs/security.md)

## License

MIT
