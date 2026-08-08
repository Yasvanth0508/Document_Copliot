import re
from bs4 import BeautifulSoup, Tag


# Common 10-K / 10-Q section header pattern matcher
ITEM_HEADER_PATTERN = re.compile(
    r"^(PART\s+[I|V|X]+|ITEM\s+(?:1A|1B|7A|[1-9][0-9]?)[A-Z]?\.?)\s*[\:\-\—\–]?\s*(.*)",
    re.IGNORECASE,
)


def parse_html_to_markdown(html_content: str) -> str:
    """Parses raw SEC filing HTML content into normalized Markdown.

    Strips scripts, inline styles, hidden XBRL elements, converts HTML tables
    to Markdown tables, and preserves Item section headers for retrieval.
    """
    if not html_content or not html_content.strip():
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Strip non-content tags
    for tag in soup(["script", "style", "noscript", "head", "iframe", "ix:header"]):
        tag.decompose()

    # 2. Strip hidden elements (XBRL display:none)
    for tag in soup.find_all(True):
        style = tag.get("style", "")
        if isinstance(style, str) and "display:none" in style.lower().replace(" ", ""):
            tag.decompose()

    # 3. Convert HTML tables to Markdown tables
    for table in soup.find_all("table"):
        markdown_table = _convert_table_to_markdown(table)
        table.replace_with(soup.new_string(f"\n\n{markdown_table}\n\n"))

    # 4. Extract text line by line and format headers
    lines: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "div"]):
        if not isinstance(element, Tag):
            continue

        text = element.get_text(separator=" ", strip=True)
        if not text:
            continue

        # Check if text matches an SEC Item section header
        match = ITEM_HEADER_PATTERN.match(text)
        if match:
            item_tag = match.group(1).upper()
            rest = match.group(2).strip()
            header_text = f"# {item_tag} {rest}".strip()
            lines.append(f"\n\n{header_text}\n\n")
        elif element.name in ["h1", "h2", "h3"]:
            lines.append(f"\n\n## {text}\n\n")
        else:
            lines.append(f"\n{text}\n")

    # Fallback if no specific tags were matched
    if not lines:
        text = soup.get_text(separator="\n", strip=True)
        return _clean_markdown(text)

    full_markdown = "".join(lines)
    return _clean_markdown(full_markdown)


def _convert_table_to_markdown(table_tag: Tag) -> str:
    """Converts a BeautifulSoup <table> tag into a clean Markdown table."""
    rows: list[list[str]] = []
    for tr in table_tag.find_all("tr"):
        row_cells: list[str] = []
        for cell in tr.find_all(["th", "td"]):
            cell_text = cell.get_text(separator=" ", strip=True).replace("|", "\\|")
            # Compress multiple spaces
            cell_text = re.sub(r"\s+", " ", cell_text)
            row_cells.append(cell_text or "-")
        if row_cells and any(c != "-" for c in row_cells):
            rows.append(row_cells)

    if not rows:
        return ""

    # Normalize column count across all rows
    max_cols = max(len(r) for r in rows)
    normalized_rows = [r + ["-"] * (max_cols - len(r)) for r in rows]

    header_row = normalized_rows[0]
    separator_row = ["---"] * max_cols
    body_rows = normalized_rows[1:]

    lines = [
        "| " + " | ".join(header_row) + " |",
        "| " + " | ".join(separator_row) + " |",
    ]
    for row in body_rows:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _clean_markdown(text: str) -> str:
    """Normalizes whitespace and consecutive blank lines in Markdown output."""
    # Replace non-breaking spaces
    text = text.replace("\xa0", " ").replace("\u200b", "")
    # Compress 3 or more blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
