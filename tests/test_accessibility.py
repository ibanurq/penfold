"""What screen readers say for the rows of the side panel, which GTK does not name by itself."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Gtk

from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_bookmarks import add_outline
from tests.test_page_content import make_text_pdf
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def window(application: "PenfoldApplication") -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    yield new_window
    new_window.destroy()
    process_pending_events()


@pytest.fixture
def named_items(monkeypatch: pytest.MonkeyPatch) -> list[Gtk.ListItem]:
    """The list items the panel's views give a name to, in the order they do."""
    from penfold.ui.sidebar import annotations_view, bookmarks_view, search_view, view_header

    items: list[Gtk.ListItem] = []

    def name_row(item: Gtk.ListItem, *parts: str) -> None:
        items.append(item)
        view_header.name_row(item, *parts)

    for module in (annotations_view, bookmarks_view, search_view):
        monkeypatch.setattr(module, "name_row", name_row)
    return items


def names(items: list[Gtk.ListItem]) -> list[str]:
    """The names the items have now, once each, in the order they were first named."""
    return [item.get_accessible_label() or "" for item in dict.fromkeys(items)]


def test_a_row_is_named_after_its_parts_that_are_not_empty(application: "PenfoldApplication") -> None:  # noqa: ARG001
    from penfold.ui.sidebar.view_header import name_row

    item = Gtk.ListItem()
    name_row(item, "Rectangle", "Page 2", "", "No text")
    assert item.get_accessible_label() == "Rectangle, Page 2, No text"


def test_every_annotation_type_has_a_name_and_the_tools_share_it(application: "PenfoldApplication") -> None:  # noqa: ARG001
    from penfold.document.annotations import Kind
    from penfold.ui.annotation_icons import kind_names
    from penfold.ui.annotation_toolbar import Tool, tool_names

    kinds = kind_names()
    assert set(kinds) == set(Kind)
    tools = tool_names()
    assert set(tools) == set(Tool)
    assert all(tools[tool] == kinds[tool.kind] for tool in Tool if tool.kind is not None)
    assert tools[Tool.SELECT] == "Select Text"


def test_bookmark_rows_say_their_title_and_page(
    window: "PenfoldWindow", tmp_path: Path, named_items: list[Gtk.ListItem]
) -> None:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    window.sidebar.show_view("bookmarks")
    wait_until(lambda: len(names(named_items)) == 5)
    # GTK binds the rows in no set order: the child row comes after the others.
    assert sorted(names(named_items)) == [
        "1. Intro, Page 2",
        "1.1 Scope, Page 3",
        "Action, Page 5",
        "Broken",
        "Cover, Page 1",
    ]


def test_annotation_rows_say_the_type_shown_as_an_icon_and_the_text_read_later(
    window: "PenfoldWindow", tmp_path: Path, named_items: list[Gtk.ListItem]
) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        # A highlight over "Page 1 line 1": its text is read from the page after the row is shown.
        highlight = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Highlight,
            Rect=[70, 736, 170, 756],
            QuadPoints=[70, 756, 170, 756, 70, 736, 170, 736],
            T=pikepdf.String("Ana"),
        )
        square = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Square, Rect=[50, 50, 90, 90])
        pdf.pages[0].Annots = pdf.make_indirect(
            pikepdf.Array([pdf.make_indirect(highlight), pdf.make_indirect(square)])
        )
        pdf.save(path)
    open_and_wait(window, path)
    window.sidebar.show_view("annotations")
    wait_until(lambda: any("line 1" in name for name in names(named_items)))
    assert names(named_items) == ["Highlight, Page 1, Ana, “Page 1 line 1”", "Rectangle, Page 1, (External), No text"]


def test_find_results_say_their_page_and_sentence(
    window: "PenfoldWindow", tmp_path: Path, named_items: list[Gtk.ListItem]
) -> None:
    open_and_wait(window, make_text_pdf(tmp_path / "text.pdf"))
    window.activate_action("win.find", None)
    search = window.search_view
    search.entry.set_text("line 2")
    wait_until(lambda: search.results.get_n_items() == 3 and not search._searching)
    wait_until(lambda: len(names(named_items)) == 3 and all("line 2" in name for name in names(named_items)))
    assert names(named_items) == [f"Page {page}, Page {page} line 2" for page in (1, 2, 3)]
