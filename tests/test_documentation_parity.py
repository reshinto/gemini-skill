"""Documentation parity checks for the public entry points and references."""

from __future__ import annotations

from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


class TestReadmeParity:
    def test_readme_mentions_skill_and_cli_usage(self) -> None:
        readme_path: Path = _repository_root() / "README.md"
        readme_text: str = readme_path.read_text(encoding="utf-8")

        assert "Claude Code skill" in readme_text
        assert "direct CLI" in readme_text
        assert "python3 scripts/gemini_run.py" in readme_text


class TestReferenceParity:
    def test_reference_index_lists_plan_review(self) -> None:
        reference_index_path: Path = _repository_root() / "reference" / "index.md"
        reference_index_text: str = reference_index_path.read_text(encoding="utf-8")

        assert "`plan_review`" in reference_index_text
        assert "[plan_review.md](plan_review.md)" in reference_index_text

    def test_commands_doc_lists_plan_review(self) -> None:
        commands_doc_path: Path = _repository_root() / "docs" / "commands.md"
        commands_doc_text: str = commands_doc_path.read_text(encoding="utf-8")

        assert "`plan_review`" in commands_doc_text

    def test_plan_review_reference_exists(self) -> None:
        plan_review_reference_path: Path = _repository_root() / "reference" / "plan_review.md"

        assert plan_review_reference_path.is_file()
