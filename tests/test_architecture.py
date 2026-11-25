"""The layers only depend on each other in one direction."""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGE_DIRECTORY = Path(__file__).parent.parent / "penfold"

FORBIDDEN_IMPORTS = {
    "document": ("gi", "cairo", "penfold.rendering", "penfold.ui", "penfold.application"),
    "rendering": ("penfold.ui", "penfold.application"),
}


def imported_modules(source_file: Path) -> Iterator[str]:
    """Yield the absolute name of every module imported by a Python file."""
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def is_within(module: str, package: str) -> bool:
    """Tell whether a module is a package or one of its submodules."""
    return module == package or module.startswith(f"{package}.")


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_layer_does_not_import_upper_layers(layer: str) -> None:
    violations = [
        f"{source_file.relative_to(PACKAGE_DIRECTORY)} imports {module}"
        for source_file in sorted((PACKAGE_DIRECTORY / layer).rglob("*.py"))
        for module in imported_modules(source_file)
        if any(is_within(module, forbidden) for forbidden in FORBIDDEN_IMPORTS[layer])
    ]
    assert not violations, "\n".join(violations)


def test_relative_imports_are_not_used() -> None:
    relative_imports = [
        str(source_file.relative_to(PACKAGE_DIRECTORY))
        for source_file in sorted(PACKAGE_DIRECTORY.rglob("*.py"))
        for node in ast.walk(ast.parse(source_file.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.level > 0
    ]
    assert not relative_imports, "Use absolute imports so the layer rule can be checked: " + ", ".join(relative_imports)
