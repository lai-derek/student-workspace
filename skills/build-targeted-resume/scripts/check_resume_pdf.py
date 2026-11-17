"""Check a compiled one-page resume's text, page geometry, and links."""

from __future__ import annotations

import argparse
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--expect", action="append", default=[], help="Text that must extract")
    parser.add_argument("--require-link", action="append", default=[], help="URI substring")
    args = parser.parse_args()

    errors: list[str] = []
    if not args.pdf.is_file() or args.pdf.stat().st_size == 0:
        print(f"ERROR: missing or empty PDF: {args.pdf}")
        return 1

    with pdfplumber.open(args.pdf) as document:
        if len(document.pages) != 1:
            errors.append(f"expected one page, found {len(document.pages)}")
        if not document.pages:
            print("ERROR: PDF contains no pages")
            return 1
        page = document.pages[0]
        if abs(page.width - 612) > 1 or abs(page.height - 792) > 1:
            errors.append(f"expected US Letter, found {page.width:g} x {page.height:g} pt")
        text = page.extract_text() or ""
        if len(text.strip()) < 100:
            errors.append("little or no searchable text")
        for required in args.expect:
            if required.casefold() not in text.casefold():
                errors.append(f"missing extracted text: {required}")

        chars = [char for char in page.chars if str(char.get("text", "")).strip()]
        if not chars:
            errors.append("no positioned text characters")
        else:
            left = min(char["x0"] for char in chars)
            right = max(char["x1"] for char in chars)
            top = min(char["top"] for char in chars)
            bottom = max(char["bottom"] for char in chars)
            print(
                "Text bounds (pt): "
                f"left={left:.1f}, right={page.width - right:.1f}, "
                f"top={top:.1f}, bottom={page.height - bottom:.1f}"
            )
            if min(left, page.width - right, top, page.height - bottom) < 24:
                errors.append("text comes within 24 pt of a page edge")

    reader = PdfReader(args.pdf)
    uris: list[str] = []
    for page in reader.pages:
        for annotation in page.get("/Annots", []):
            entry = annotation.get_object()
            action = entry.get("/A")
            if action and action.get("/URI"):
                uris.append(str(action["/URI"]))
    for required in args.require_link:
        if not any(required.casefold() in uri.casefold() for uri in uris):
            errors.append(f"missing URI link: {required}")
    print(f"Page count: {len(reader.pages)}; URI links: {len(uris)}")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
