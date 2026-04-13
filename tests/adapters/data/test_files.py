"""Tests for adapters/data/files.py — File API adapter."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


class TestFilesGetParser:
    def test_has_upload_action(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["upload", "test.pdf"])
        assert args.action == "upload"
        assert args.path == "test.pdf"

    def test_has_list_action(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["list"])
        assert args.action == "list"

    def test_has_get_action(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["get", "files/abc"])
        assert args.action == "get"
        assert args.name == "files/abc"

    def test_has_delete_action(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["delete", "files/abc"])
        assert args.action == "delete"

    def test_mutating_subcommands_accept_execute(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["upload", "test.pdf", "--execute"])
        assert args.execute is True

        args = get_parser().parse_args(["delete", "files/abc", "--execute"])
        assert args.execute is True

    def test_has_download_action(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["download", "files/abc", "/tmp/out.bin"])
        assert args.action == "download"
        assert args.name == "files/abc"
        assert args.out_path == "/tmp/out.bin"

    def test_download_accepts_execute(self):
        from adapters.data.files import get_parser

        args = get_parser().parse_args(["download", "files/abc", "/tmp/out.bin", "--execute"])
        assert args.execute is True

    def test_read_only_subcommands_reject_execute(self):
        from adapters.data.files import get_parser

        parser = get_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["list", "--execute"])
        with pytest.raises(SystemExit):
            parser.parse_args(["get", "files/abc", "--execute"])


class TestFilesDownload:
    def test_dry_run_skips_download(self, capsys, tmp_path):
        from adapters.data.files import run

        out = tmp_path / "out.bin"
        run(action="download", name="files/abc", out_path=str(out), execute=False)
        captured = capsys.readouterr().out
        assert "[DRY RUN]" in captured
        assert not out.exists()

    def test_download_no_name_shows_error(self, capsys):
        from adapters.data.files import run

        run(action="download", name=None, out_path="/tmp/out.bin", execute=True)
        assert "[ERROR]" in capsys.readouterr().out

    def test_download_no_out_path_shows_error(self, capsys):
        from adapters.data.files import run

        run(action="download", name="files/abc", out_path=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out

    def test_download_writes_bytes_to_path(self, tmp_path, capsys):
        from adapters.data.files import run

        out = tmp_path / "out.bin"
        with patch(
            "adapters.data.files.download_file_bytes",
            return_value=b"\x00\x01\x02hello",
        ) as mock:
            run(
                action="download",
                name="files/abc",
                out_path=str(out),
                execute=True,
            )
        mock.assert_called_once_with("files/abc")
        assert out.read_bytes() == b"\x00\x01\x02hello"

    def test_download_emits_json_summary(self, tmp_path, capsys):
        from adapters.data.files import run

        out = tmp_path / "out.bin"
        with patch(
            "adapters.data.files.download_file_bytes",
            return_value=b"hello world",
        ):
            run(
                action="download",
                name="files/abc",
                out_path=str(out),
                execute=True,
            )
        data = json.loads(capsys.readouterr().out)
        assert data["path"] == str(out)
        assert data["name"] == "files/abc"
        assert data["size_bytes"] == len(b"hello world")

    def test_download_creates_parent_dirs(self, tmp_path, capsys):
        """Nested output paths with non-existent parents should
        auto-create the directory so users don't have to precompute
        a mkdir step before every download."""
        from adapters.data.files import run

        out = tmp_path / "nested" / "dir" / "out.bin"
        with patch(
            "adapters.data.files.download_file_bytes",
            return_value=b"abc",
        ):
            run(
                action="download",
                name="files/abc",
                out_path=str(out),
                execute=True,
            )
        assert out.read_bytes() == b"abc"


class TestFilesUpload:
    def test_dry_run_skips_upload(self, capsys):
        from adapters.data.files import run

        run(action="upload", path="test.pdf", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_upload_calls_upload_file(self, tmp_path, capsys):
        from adapters.data.files import run

        f = tmp_path / "test.txt"
        f.write_text("content")

        with patch(
            "adapters.data.files.upload_file",
            return_value={"file": {"name": "files/x", "uri": "gs://x"}},
        ) as mock:
            run(action="upload", path=str(f), execute=True)
        mock.assert_called_once()

    def test_upload_no_path_shows_error(self, capsys):
        from adapters.data.files import run

        run(action="upload", path=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out

    def test_upload_emits_json(self, tmp_path, capsys):
        from adapters.data.files import run

        f = tmp_path / "test.txt"
        f.write_text("content")

        with patch(
            "adapters.data.files.upload_file",
            return_value={"file": {"name": "files/x", "uri": "gs://x"}},
        ):
            run(action="upload", path=str(f), execute=True)
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "files/x"


class TestFilesList:
    def test_list_files(self, capsys):
        from adapters.data.files import run

        with patch("adapters.data.files.api_call", return_value={"files": [{"name": "files/a"}]}):
            run(action="list")
        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 1


class TestFilesGet:
    def test_get_file(self, capsys):
        from adapters.data.files import run

        with patch(
            "adapters.data.files.api_call", return_value={"name": "files/a", "state": "ACTIVE"}
        ):
            run(action="get", name="files/a")
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "files/a"

    def test_get_no_name_shows_error(self, capsys):
        from adapters.data.files import run

        run(action="get", name=None)
        assert "[ERROR]" in capsys.readouterr().out


class TestFilesDelete:
    def test_dry_run_skips_delete(self, capsys):
        from adapters.data.files import run

        run(action="delete", name="files/a", execute=False)
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_delete_calls_api(self, capsys):
        from adapters.data.files import run

        with patch("adapters.data.files.api_call") as mock:
            run(action="delete", name="files/a", execute=True)
        mock.assert_called_once()

    def test_delete_no_name_shows_error(self, capsys):
        from adapters.data.files import run

        run(action="delete", name=None, execute=True)
        assert "[ERROR]" in capsys.readouterr().out


class TestFilesNoAction:
    def test_no_action_shows_error(self, capsys):
        from adapters.data.files import run

        run(action=None)
        assert "[ERROR]" in capsys.readouterr().out
