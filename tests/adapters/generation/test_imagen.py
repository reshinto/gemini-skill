"""Tests for adapters/generation/imagen.py — Imagen text-to-image adapter.

Imagen is the google-genai SDK's dedicated photoreal image model surface
(``client.models.generate_images``), distinct from the Gemini-native
image generation the existing image_gen adapter exposes. The Imagen
path is SDK-only — there is no raw HTTP REST endpoint this skill
supports for it — so the adapter calls ``get_client()`` directly and
does its own response normalization, bypassing the dual-backend
coordinator for this one capability.

Every test mocks ``core.transport.sdk.client_factory.get_client``;
no live network.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_generated_image(data: bytes = b"\x89PNG-imagen-bytes") -> MagicMock:
    """Build a mock GeneratedImage with the shape the adapter reads.

    google-genai's GeneratedImage carries ``image.image_bytes`` (raw
    bytes) for the generated file — the adapter writes those bytes
    directly to disk without any base64 decoding step.
    """
    generated = MagicMock(name="GeneratedImage")
    generated.image = MagicMock(name="Image")
    generated.image.image_bytes = data
    generated.image.mime_type = "image/png"
    return generated


def _make_imagen_response(*, num: int = 1, data: bytes = b"\x89PNG") -> MagicMock:
    """Build a mock GenerateImagesResponse with ``num`` images."""
    response = MagicMock(name="GenerateImagesResponse")
    response.generated_images = [_make_generated_image(data) for _ in range(num)]
    return response


@pytest.fixture
def patched_client() -> MagicMock:
    """Return a mocked SDK client wired with a models.generate_images method."""
    client = MagicMock(name="genai.Client")
    client.models = MagicMock(name="client.models")
    client.models.generate_images = MagicMock(return_value=_make_imagen_response())
    return client


@pytest.fixture(autouse=True)
def _reset_client_cache() -> Iterator[None]:
    """Drop any SDK client lru_cache so each test constructs fresh."""
    from core.transport.sdk import client_factory

    client_factory.get_client.cache_clear()
    yield
    client_factory.get_client.cache_clear()


class TestImagenGetParser:
    def test_has_prompt(self) -> None:
        from adapters.generation.imagen import get_parser

        args = get_parser().parse_args(["a calico cat"])
        assert args.prompt == "a calico cat"

    def test_defaults(self) -> None:
        from adapters.generation.imagen import get_parser

        args = get_parser().parse_args(["cat"])
        assert args.num_images == 1
        assert args.output_dir is None
        assert args.aspect_ratio is None

    def test_has_num_images(self) -> None:
        from adapters.generation.imagen import get_parser

        args = get_parser().parse_args(["cat", "--num-images", "4"])
        assert args.num_images == 4

    def test_has_aspect_ratio(self) -> None:
        from adapters.generation.imagen import get_parser

        args = get_parser().parse_args(["cat", "--aspect-ratio", "16:9"])
        assert args.aspect_ratio == "16:9"

    def test_rejects_invalid_aspect_ratio(self) -> None:
        from adapters.generation.imagen import get_parser

        with pytest.raises(SystemExit):
            get_parser().parse_args(["cat", "--aspect-ratio", "bogus"])

    def test_rejects_num_images_zero(self) -> None:
        from adapters.generation.imagen import get_parser

        with pytest.raises(SystemExit):
            get_parser().parse_args(["cat", "--num-images", "0"])


class TestImagenRun:
    def test_dry_run_skips(self, capsys: pytest.CaptureFixture[str]) -> None:
        from adapters.generation.imagen import run

        run(prompt="cat", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_saves_single_image(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from adapters.generation.imagen import run

        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="a calico cat", execute=True)

        output = capsys.readouterr().out
        data = json.loads(output)
        # First (only) image is at path with saved bytes
        assert data["count"] == 1
        assert len(data["images"]) == 1
        saved_path = data["images"][0]["path"]
        assert Path(saved_path).exists()
        assert Path(saved_path).read_bytes() == b"\x89PNG"
        assert data["images"][0]["mime_type"] == "image/png"

    def test_passes_prompt_and_num_images_to_sdk(
        self, patched_client: MagicMock, tmp_path: Path
    ) -> None:
        from adapters.generation.imagen import run

        patched_client.models.generate_images.return_value = _make_imagen_response(num=3)
        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="mountain sunset", execute=True, num_images=3)

        call = patched_client.models.generate_images.call_args
        assert call.kwargs["prompt"] == "mountain sunset"
        # config carries number_of_images
        cfg = call.kwargs["config"]
        assert cfg.number_of_images == 3

    def test_passes_aspect_ratio_to_config(self, patched_client: MagicMock, tmp_path: Path) -> None:
        from adapters.generation.imagen import run

        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True, aspect_ratio="16:9")

        call = patched_client.models.generate_images.call_args
        assert call.kwargs["config"].aspect_ratio == "16:9"

    def test_saves_multiple_images_with_distinct_paths(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from adapters.generation.imagen import run

        patched_client.models.generate_images.return_value = _make_imagen_response(num=3)
        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True, num_images=3)

        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 3
        paths = [item["path"] for item in data["images"]]
        assert len(set(paths)) == 3  # All distinct
        for p in paths:
            assert Path(p).exists()

    def test_never_outputs_base64(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Bytes must land on disk, not in stdout — Claude Code would
        tokenize a large base64 blob on every read."""
        from adapters.generation.imagen import run

        big = b"\x89PNG" * 1000
        patched_client.models.generate_images.return_value = _make_imagen_response(data=big)
        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True)

        out = capsys.readouterr().out
        assert base64.b64encode(big).decode() not in out

    def test_positive_int_rejects_non_numeric(self) -> None:
        """``argparse`` feeds ``_positive_int`` the raw string. Non-numeric
        input must raise ValueError so argparse surfaces it as a clean
        usage error instead of a traceback."""
        from adapters.generation.imagen import _positive_int

        with pytest.raises(ValueError, match="invalid int"):
            _positive_int("abc")

    def test_skips_items_without_image_bytes(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A GeneratedImage with ``image.image_bytes=None`` is skipped
        silently so partial responses don't crash the write loop."""
        from adapters.generation.imagen import run

        good = _make_generated_image(b"OK")
        missing_image = MagicMock()
        missing_image.image = None
        missing_bytes = MagicMock()
        missing_bytes.image = MagicMock()
        missing_bytes.image.image_bytes = None
        missing_bytes.image.mime_type = "image/png"
        resp = MagicMock()
        resp.generated_images = [missing_image, missing_bytes, good]
        patched_client.models.generate_images.return_value = resp

        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True)

        data = json.loads(capsys.readouterr().out)
        # Only the one good image is saved.
        assert data["count"] == 1
        assert Path(data["images"][0]["path"]).read_bytes() == b"OK"

    def test_all_items_without_bytes_prints_warn(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """If every item is skipped, emit a WARN so the user sees the
        degenerate case instead of a silent success."""
        from adapters.generation.imagen import run

        bad = MagicMock()
        bad.image = None
        resp = MagicMock()
        resp.generated_images = [bad]
        patched_client.models.generate_images.return_value = resp

        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True)

        assert "WARN" in capsys.readouterr().out

    def test_mime_type_none_defaults_to_png(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A generated image with ``mime_type=None`` must fall back to
        ``image/png`` so the file gets a usable extension on disk."""
        from adapters.generation.imagen import run

        item = MagicMock()
        item.image = MagicMock()
        item.image.image_bytes = b"data"
        item.image.mime_type = None
        resp = MagicMock()
        resp.generated_images = [item]
        patched_client.models.generate_images.return_value = resp

        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True)

        data = json.loads(capsys.readouterr().out)
        assert data["images"][0]["mime_type"] == "image/png"

    def test_empty_response_prints_warning(
        self, patched_client: MagicMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The SDK occasionally returns an empty ``generated_images`` list
        (safety filters / model refusal). The adapter must print a clear
        message instead of silently succeeding."""
        from adapters.generation.imagen import run

        empty_resp = MagicMock()
        empty_resp.generated_images = []
        patched_client.models.generate_images.return_value = empty_resp
        with (
            patch("adapters.generation.imagen.get_client", return_value=patched_client),
            patch("adapters.generation.imagen.load_config") as mock_cfg,
        ):
            mock_cfg.return_value = MagicMock(prefer_preview_models=False, output_dir=str(tmp_path))
            run(prompt="cat", execute=True)
        assert "No images" in capsys.readouterr().out
