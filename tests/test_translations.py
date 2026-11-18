"""Every text of the interface can be translated, and the Spanish translation is complete (03-arquitectura, 7)."""

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_DIRECTORY = Path(__file__).parent.parent
PO_DIRECTORY = PROJECT_DIRECTORY / "po"
COMPLETE_LANGUAGES = ("es",)

# The same keywords as po/meson.build, on top of xgettext's defaults for C (Blueprint) and Python.
XGETTEXT_KEYWORDS = ("--keyword=_", "--keyword=C_:1c,2", "--keyword=pgettext:1c,2", "--keyword=npgettext:1c,2,3")
TRANSLATABLE_TEXT = re.compile(r"\b(_|C_|ngettext|pgettext|npgettext)\(")


def listed_source_files() -> list[str]:
    lines = (PO_DIRECTORY / "POTFILES.in").read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def test_languages_are_listed() -> None:
    languages = (PO_DIRECTORY / "LINGUAS").read_text(encoding="utf-8").split()
    assert sorted(languages) == sorted(path.stem for path in PO_DIRECTORY.glob("*.po"))


def test_every_file_with_translatable_texts_is_listed() -> None:
    candidates = [*PROJECT_DIRECTORY.glob("penfold/**/*.py"), *PROJECT_DIRECTORY.glob("data/ui/*.blp")]
    files_with_texts = {
        str(path.relative_to(PROJECT_DIRECTORY))
        for path in candidates
        if TRANSLATABLE_TEXT.search(path.read_text(encoding="utf-8"))
    }
    assert files_with_texts <= set(listed_source_files())


@pytest.mark.parametrize("language", COMPLETE_LANGUAGES)
def test_translation_is_complete(language: str, tmp_path: Path) -> None:
    template = tmp_path / "penfold.pot"
    subprocess.run(
        ["xgettext", "--from-code=UTF-8", *XGETTEXT_KEYWORDS, "--output", str(template), *listed_source_files()],
        cwd=PROJECT_DIRECTORY,
        check=True,
        capture_output=True,
    )
    # msgcmp fails if a text of the template is missing, untranslated or fuzzy in the translation.
    result = subprocess.run(
        ["msgcmp", str(PO_DIRECTORY / f"{language}.po"), str(template)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("language", COMPLETE_LANGUAGES)
def test_translation_file_is_valid(language: str) -> None:
    result = subprocess.run(
        ["msgfmt", "--check", "--output-file=/dev/null", str(PO_DIRECTORY / f"{language}.po")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
