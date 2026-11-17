#!/usr/bin/env python3
"""Render Linktree links as a Zola links page."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "linktree-link-extractor/1.0"


class NextDataParser(HTMLParser):
    """Collect the JSON stored in Linktree's __NEXT_DATA__ script element."""

    def __init__(self) -> None:
        super().__init__()
        self._capturing = False
        self._chunks: list[str] = []
        self.data: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "script":
            return

        attributes = dict(attrs)
        if attributes.get("id") == "__NEXT_DATA__":
            if self.data is not None or self._capturing:
                raise ValueError("Linktree page contains multiple __NEXT_DATA__ scripts")
            self._capturing = True

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capturing:
            self._capturing = False
            self.data = "".join(self._chunks)


def fetch_linktree_page(linktree_url: str) -> str:
    request = Request(
        linktree_url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": USER_AGENT,
        },
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def extract_links(page_html: str) -> list[tuple[str, str]]:
    parser = NextDataParser()
    parser.feed(page_html)

    if parser.data is None:
        raise ValueError("Linktree page does not contain a __NEXT_DATA__ payload")

    try:
        payload: Any = json.loads(parser.data)
        raw_links = payload["props"]["pageProps"]["links"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("Linktree returned an unexpected data payload") from error

    if not isinstance(raw_links, list):
        raise ValueError("Linktree links payload is not a list")

    positioned_links: list[tuple[int, str, str]] = []
    for fallback_position, item in enumerate(raw_links):
        if not isinstance(item, dict):
            raise ValueError("Linktree links payload contains a non-object item")

        url = item.get("url")
        if not isinstance(url, str) or not url:
            # Headers and other non-link page elements have no destination URL.
            continue

        title = item.get("title")
        if not isinstance(title, str) or not title:
            raise ValueError(f"Linktree link at index {fallback_position} has no title")

        position = item.get("position", fallback_position)
        if not isinstance(position, int):
            position = fallback_position

        positioned_links.append((position, title, url))

    if not positioned_links:
        raise ValueError("Linktree page contains no links")

    positioned_links.sort(key=lambda link: link[0])
    return [(title, url) for _, title, url in positioned_links]


def toml_string(value: str) -> str:
    """Encode a string using syntax valid for a TOML basic string."""

    return json.dumps(value, ensure_ascii=False)


def render_links_page(links: list[tuple[str, str]]) -> str:
    lines = [
        "+++",
        'title = "Links"',
        'template = "links.html"',
        "",
    ]

    for title, url in links:
        lines.extend(
            [
                "[[extra.links]]",
                f"name = {toml_string(title)}",
                f"url = {toml_string(url)}",
                "",
            ]
        )

    lines.append("+++")
    return "\n".join(lines) + "\n"


def write_atomically(output_path: Path, contents: str) -> None:
    parent = output_path.parent
    if not parent.is_dir():
        raise ValueError(f"Output directory does not exist: {parent}")

    existing_mode = (
        stat.S_IMODE(output_path.stat().st_mode) if output_path.exists() else 0o644
    )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=parent,
        prefix=f".{output_path.name}.",
        text=True,
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        temporary_path.chmod(existing_mode)
        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract Linktree titles and URLs and render a complete Zola links "
            "Markdown page."
        )
    )
    parser.add_argument(
        "linktree_url",
        metavar="LINKTREE_URL",
        help="URL of the Linktree page to extract",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write atomically to this path instead of printing to stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        page_html = fetch_linktree_page(args.linktree_url)
        links = extract_links(page_html)
        document = render_links_page(links)

        if args.output is None:
            sys.stdout.write(document)
        else:
            write_atomically(args.output, document)
    except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
