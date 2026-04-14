# embed

Generate vector embeddings for text. Returns embedding dimensions and values as JSON.

## Usage

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gemini_run.py" embed "text" [--task-type type]
```

## Flags

- `--task-type TYPE` — Embedding task type (e.g., `RETRIEVAL_DOCUMENT`, `RETRIEVAL_QUERY`, `SEMANTIC_SIMILARITY`).
- `--model MODEL` — Override the default model.

## Examples

```bash
# Embed a simple phrase
gemini_run.py embed "machine learning is powerful"

# Embed for retrieval (document)
gemini_run.py embed "Dense passage of text from a knowledge base" --task-type RETRIEVAL_DOCUMENT

# Embed a query
gemini_run.py embed "How do neural networks work?" --task-type RETRIEVAL_QUERY

# Similarity matching
gemini_run.py embed "Text sample" --task-type SEMANTIC_SIMILARITY
```

## Output format

```json
{
  "model": "embedding-model-name",
  "dimensions": 768,
  "values": [0.123, -0.456, ...]
}
```

## Default model

`gemini-embedding-2-preview` (set as `default_model` for the `embed` capability in [registry/capabilities.json](../registry/capabilities.json); it is the only model registered in [registry/models.json](../registry/models.json) that declares the `embed` capability). To pin a different embedding model, add it to `registry/models.json` with `"capabilities": ["embed"]` and pass `--model <id>`.

## Use case

Embeddings are used for semantic search, retrieval-augmented generation (RAG), and similarity comparisons. Store the returned `values` array in a vector database.

---

Backend-agnostic: this command produces identical output whether the SDK or raw HTTP backend handled the call.
