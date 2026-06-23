"""Shared low-level primitives for the hand-rolled markdown tables in the CRM /
opportunity vault files (crm.md, ledger.md, dm-queue.md).

These replace the cell-split / row-filter loops that were copy-pasted across the
dashboard and the outreach/opportunity tools. Intentionally tiny and dependency-free
(no imports from sibling tools) so it can't introduce import cycles.
"""

from collections.abc import Callable, Iterator


def split_cells(line: str) -> list[str]:
    """Split one markdown table line into its trimmed cell strings.

    Mirrors the `[c.strip() for c in line.strip("|").split("|")]` used everywhere:
    strip the outer pipes, split on the inner ones, trim each cell.
    """
    return [c.strip() for c in line.strip("|").split("|")]


def clean_cell(s: str) -> str:
    """Sanitize a value for one table cell: pipes/newlines would corrupt the row a
    human (or the dashboard) reads, so collapse them. Shared by outreach_crm._clean
    and social_dm._clean_cell (which were byte-identical)."""
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def table_rows(
    text: str,
    *,
    strip_line: bool = True,
    is_header: Callable[[str], bool] | None = None,
    is_divider: Callable[[str], bool] | None = None,
) -> Iterator[list[str]]:
    """Yield the trimmed cell lists for each *data* row in a markdown table.

    Skips lines that aren't table rows (no leading `|`), the `|---|` divider, and the
    header row. The exact header/divider detection differs slightly between the CRM and
    the opportunity ledger, so each call site passes its own ``is_header`` / ``is_divider``
    predicate (operating on the — optionally stripped — line) to preserve its behavior
    verbatim. Both predicates default to a no-op (skip nothing extra).

    ``strip_line`` controls whether each raw line is ``.strip()``-ed before the leading-`|`
    check and before being handed to the predicates / ``split_cells`` — matching the sites
    that pre-strip the line and those that don't.
    """
    for raw in text.splitlines():
        line = raw.strip() if strip_line else raw
        if not line.startswith("|"):
            continue
        if is_divider is not None and is_divider(line):
            continue
        if is_header is not None and is_header(line):
            continue
        yield split_cells(line)
