# Capabilities — Media

[← Back to README](../README.md) · [Docs index](README.md) · [Reference index](../reference/index.md)

---

**Last Updated:** 2026-04-18

Commands for generating images, video, and music, each with dry-run-first semantics and per-model routing.

## Commands in this category

- `image_gen` → [image_gen.md](../reference/image_gen.md)
- `imagen` → [imagen.md](../reference/imagen.md)
- `video_gen` → [video_gen.md](../reference/video_gen.md)
- `music_gen` → [music_gen.md](../reference/music_gen.md)

---

### Image generation

**Status:** Preview (v1beta, may change)

Generate images using the Nano Banana model.

**Capabilities:**
- Text-to-image generation
- Fast turnaround (5–10s)
- PNG output saved to file
- Aspect ratio control (`--aspect-ratio`: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9)
- Image size options (`--image-size`: 1K, 2K, 4K)

**Limitations:**
- Requires `--execute` flag (mutating)
- Nano Banana is cost-optimized (lower quality than others)
- Cannot edit or modify images
- 1 image per request

**Use cases:**
- Quick visual content generation
- Illustration for documents
- UI/UX mockup generation
- Educational diagrams

See [image_gen.md](../reference/image_gen.md).

### Imagen (Imagen 3)

**Status:** Preview (SDK-only)

Generate photoreal images using Google's dedicated Imagen 3 model.

**Capabilities:**
- Photoreal text-to-image generation
- Multiple aspect ratios (1:1, 3:4, 4:3, 9:16, 16:9, and others)
- Batch generation (up to 4 images per request)
- Higher quality than Nano Banana

**Limitations:**
- SDK-only (no raw HTTP fallback)
- Requires `--execute` flag (mutating)
- Higher cost than Nano Banana
- Slower generation (10–30s typical)

**Use cases:**
- High-quality marketing and product imagery
- Professional visual content
- Photoreal illustrations
- Detailed background generation

See [imagen.md](../reference/imagen.md).

### Video generation

**Status:** Preview (v1beta, may change)

Generate videos using the Veo model.

**Capabilities:**
- Text-to-video generation
- 4–10 second videos
- MP4 output saved to file
- Long-running (polling required)

**Limitations:**
- Requires `--execute` flag (mutating)
- Slow (1–2 minutes typical)
- High cost per generation
- Async: must poll for completion
- Output quality may vary

**Use cases:**
- Animated explanations
- Visual storytelling
- Marketing video content
- Educational video generation

See [video_gen.md](../reference/video_gen.md).

### Music generation

**Status:** Preview (v1beta, may change)

Generate music using the Lyria 3 model.

**Capabilities:**
- Text-to-music generation
- SynthID watermark (audio identification)
- WAV output saved to file
- 30-second maximum duration

**Limitations:**
- Requires `--execute` flag (mutating)
- 30-second cap (no longer tracks)
- SynthID watermark embedded (may be audible)
- High cost per generation
- Non-commercial by default (check license)
- Currently routed via the raw HTTP backend at runtime (SDK 1.33.0 does not expose this surface)

**Use cases:**
- Background music for videos
- Soundtrack generation
- Audio branding
- Musical composition assistance

See [music_gen.md](../reference/music_gen.md).

---

## See also

- [capabilities.md](capabilities.md) — category index
- [commands.md](commands.md) — command routing
- [reference/index.md](../reference/index.md) — per-command reference
