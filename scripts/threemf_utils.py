#!/usr/bin/env python3

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn
from zipfile import ZIP_DEFLATED, ZipFile


def cli_entry(main: Callable[[], int]) -> NoReturn:
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)


def format_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def find_child_by_attr(
    element: ET.Element,
    tag: str,
    attr: str,
    value: str,
) -> ET.Element | None:
    for child in element.findall(tag):
        if child.get(attr) == value:
            return child
    return None


def find_metadata(element: ET.Element, key: str) -> ET.Element | None:
    return find_child_by_attr(element, "metadata", "key", key)


def set_metadata(element: ET.Element, key: str, value: str) -> None:
    existing = find_metadata(element, key)
    if existing is not None:
        existing.set("value", value)
        return
    ET.SubElement(element, "metadata", {"key": key, "value": value})


def rewrite_zip(
    template_path: Path,
    output_path: Path,
    patches: dict[str, Callable[[bytes], bytes]] | None = None,
    overrides: dict[str, bytes] | None = None,
) -> None:
    """Copy entries from template_path into output_path, with edits.

    For each entry in the template: if its name is in `overrides`, the override
    bytes are written verbatim; else if its name is in `patches`, the patch
    function rewrites the bytes; otherwise the entry is copied unchanged. Any
    override whose name is not present in the template is appended at the end.
    """
    patches = patches or {}
    overrides = overrides or {}
    written: set[str] = set()

    with (
        ZipFile(template_path, "r") as template,
        ZipFile(output_path, "w", ZIP_DEFLATED) as output,
    ):
        for info in template.infolist():
            name = info.filename
            if name in overrides:
                content = overrides[name]
            else:
                content = template.read(name)
                patch = patches.get(name)
                if patch is not None:
                    content = patch(content)
            output.writestr(info, content)
            written.add(name)

        for name, content in overrides.items():
            if name not in written:
                output.writestr(name, content)
