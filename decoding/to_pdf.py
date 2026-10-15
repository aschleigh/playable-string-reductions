"""MusicXML -> PDF (and first-page PNG) next to each file, via Verovio. Display only.

    python -m decoding.to_pdf DIR_OR_FILE [...]

Needs verovio, cairosvg, pypdf (display tools; not in the checker environment lock).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import cairosvg
import verovio
from pypdf import PdfReader, PdfWriter

OPTS = {"pageWidth": 2100, "pageHeight": 2970, "scale": 40, "footer": "none", "header": "auto",
        "adjustPageHeight": False, "breaks": "auto"}


def convert(xml: Path) -> Path:
    tk = verovio.toolkit()
    tk.setOptions(OPTS)
    tk.loadFile(str(xml))
    out = PdfWriter()
    for p in range(1, tk.getPageCount() + 1):
        svg = tk.renderToSVG(p)
        out.append(PdfReader(io.BytesIO(cairosvg.svg2pdf(bytestring=svg.encode()))))
        if p == 1:
            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(xml.with_suffix(".png")), background_color="white")
    pdf = xml.with_suffix(".pdf")
    with open(pdf, "wb") as f:
        out.write(f)
    return pdf


def main(argv=None):
    for a in (argv or sys.argv[1:]):
        p = Path(a)
        for x in sorted(p.rglob("*.musicxml") if p.is_dir() else [p]):
            print(convert(x))


if __name__ == "__main__":
    main()
