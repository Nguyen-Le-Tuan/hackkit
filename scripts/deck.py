"""Pitch deck from a text file: `make deck`  ->  docs/pitch/out/deck.pptx (+ deck.pdf, previews).

Reads docs/pitch/deck.toml (one [[slide]] per slide, with speaker notes and seconds), uses the
app's accent colour from web/config.json, places screenshots from docs/pitch/shots/ (make shots)
and checks the deck the way judges will feel it: words per slide, bullets, total time.

Slide kinds:
  title      big name + tagline (+ team, + background screenshot)
  statement  one big sentence (+ small line under it)          e.g. the problem, the hook
  bullets    title + up to 4 short bullets
  image      title + one screenshot (+ caption)                e.g. the product
  split      title + bullets on the left + screenshot on the right
  metrics    title + up to 4 big numbers with labels           e.g. impact; demo = true -> red
  steps      title + 3-4 numbered steps                        e.g. how it works
  divider    one word or line on a dark slide                  e.g. "Live demo"
  closing    the ask + links + thank you

Setup once: pip install -e ".[pitch]". PDF export needs LibreOffice (soffice); previews need
pdftoppm (poppler-utils). Both are optional: the PPTX is always written.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "docs" / "pitch" / "deck.toml"
OUT = ROOT / "docs" / "pitch" / "out"

MAX_WORDS = 40
MAX_BULLETS = 4
MAX_TITLE_CHARS = 60


@dataclass
class Theme:
    bg: str = "#071013"
    surface: str = "#0f1d22"
    text: str = "#e7f1f3"
    muted: str = "#92a9b0"
    accent: str = "#2dd4bf"
    hot: str = "#f59e0b"
    demo: str = "#ef4444"
    font: str = "Arial"


@dataclass
class Report:
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0


def rgb(hex_color: str):
    from pptx.dml.color import RGBColor

    return RGBColor.from_string(hex_color.lstrip("#").upper())


def words(*texts: Any) -> int:
    total = 0
    for text in texts:
        if isinstance(text, list | tuple):
            total += words(*text)
        elif isinstance(text, dict):
            total += words(*text.values())
        elif text:
            total += len(str(text).split())
    return total


class DeckBuilder:
    W = 13.333  # inches, 16:9
    H = 7.5

    def __init__(self, theme: Theme, base: Path, footer: str = "") -> None:
        from pptx import Presentation
        from pptx.util import Inches

        self.theme = theme
        self.base = base
        self.footer = footer
        self.prs = Presentation()
        self.prs.slide_width = Inches(self.W)
        self.prs.slide_height = Inches(self.H)
        self.blank = self.prs.slide_layouts[6]
        self.report = Report()

    # ------------------------------------------------------------------ primitives
    def _slide(self, bg: str | None = None):
        slide = self.prs.slides.add_slide(self.blank)
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = rgb(bg or self.theme.bg)
        return slide

    def _text(self, slide, text, x, y, w, h, *, size=20, color=None, bold=False, align="left",
              anchor="top", line_spacing=1.1):  # fmt: skip
        from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
        from pptx.util import Inches, Pt

        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        frame = box.text_frame
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = Inches(0.05)
        frame.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE,
                                 "bottom": MSO_ANCHOR.BOTTOM}[anchor]  # fmt: skip
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
                              "right": PP_ALIGN.RIGHT}[align]  # fmt: skip
            para.line_spacing = line_spacing
            run = para.add_run()
            run.text = str(line)
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.name = self.theme.font
            run.font.color.rgb = rgb(color or self.theme.text)
        return box

    def _rect(self, slide, x, y, w, h, color, *, radius=True, line=None):
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.util import Inches, Pt

        kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
        shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        if radius:
            shape.adjustments[0] = 0.08
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(color)
        if line:
            shape.line.color.rgb = rgb(line)
            shape.line.width = Pt(1)
        else:
            shape.line.fill.background()
        shape.shadow.inherit = False
        return shape

    def _fitted(self, rel_path, w, h) -> tuple[float, float] | None:
        """Size (inches) of an image scaled to fit a w x h box, or None if it is missing."""
        from PIL import Image

        path = (self.base / rel_path).resolve()
        if not path.exists():
            return None
        with Image.open(path) as img:
            iw, ih = img.size
        scale = min(w / iw, h / ih)
        return iw * scale, ih * scale

    def _image(self, slide, rel_path, x, y, w, h, *, label=""):
        """Fit an image inside the box, centred, keeping its aspect ratio."""
        from PIL import Image
        from pptx.util import Inches

        path = (self.base / rel_path).resolve() if rel_path else None
        if not path or not path.exists():
            self.report.warnings.append(f"{label}: image not found: {rel_path} (run make shots)")
            self._rect(slide, x, y, w, h, self.theme.surface, line=self.theme.demo)
            self._text(slide, f"Missing image\n{rel_path}\nrun: make shots", x, y, w, h,
                       size=16, color=self.theme.demo, align="center", anchor="middle")  # fmt: skip
            return
        with Image.open(path) as img:
            iw, ih = img.size
        scale = min(w / iw, h / ih)
        pw, ph = iw * scale, ih * scale
        slide.shapes.add_picture(
            str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph)
        )

    def _title(self, slide, text, *, y=0.55):
        self._text(slide, text, 0.75, y, self.W - 1.5, 1.0, size=34, bold=True)
        self._rect(slide, 0.78, y + 1.0, 0.9, 0.06, self.theme.accent, radius=False)

    def _chrome(self, slide, number: int):
        if self.footer:
            self._text(
                slide, self.footer, 0.75, self.H - 0.5, 8, 0.3, size=11, color=self.theme.muted
            )
        self._text(slide, str(number), self.W - 1.25, self.H - 0.5, 0.5, 0.3, size=11,
                   color=self.theme.muted, align="right")  # fmt: skip

    # ------------------------------------------------------------------ slide kinds
    def title(self, s):
        slide = self._slide()
        text_w = 6.4 if s.get("image") else 11.5
        if s.get("image"):
            # Product shot on the right, framed: reads better than text over a screenshot.
            box_x, box_y, box_w, box_h = 7.15, 1.15, 5.55, 5.2
            fitted = self._fitted(s["image"], box_w, box_h)
            if fitted:
                pw, ph = fitted
                fx, fy = box_x + (box_w - pw) / 2, box_y + (box_h - ph) / 2
                self._rect(slide, fx - 0.1, fy - 0.1, pw + 0.2, ph + 0.2, self.theme.surface,
                           line=self.theme.accent)  # fmt: skip
            self._image(slide, s["image"], box_x, box_y, box_w, box_h, label="title")
        if s.get("eyebrow"):
            self._text(slide, s["eyebrow"].upper(), 0.9, 2.0, text_w, 0.5, size=16, bold=True,
                       color=self.theme.accent)  # fmt: skip
        size = 60 if s.get("image") else 66
        self._text(slide, s.get("title", ""), 0.9, 2.45, text_w, 1.6, size=size, bold=True)
        self._text(
            slide, s.get("subtitle", ""), 0.9, 4.05, text_w, 1.3, size=26, color=self.theme.muted
        )
        if s.get("team"):
            self._text(slide, s["team"], 0.9, 6.1, text_w, 0.6, size=16, color=self.theme.muted)
        return slide

    def statement(self, s):
        slide = self._slide()
        if s.get("eyebrow"):
            self._text(slide, s["eyebrow"].upper(), 0.9, 1.6, 11, 0.5, size=16, bold=True,
                       color=self.theme.accent)  # fmt: skip
        self._text(slide, s.get("text", ""), 0.9, 2.1, 11.5, 2.6, size=48, bold=True,
                   line_spacing=1.05)  # fmt: skip
        if s.get("subtext"):
            self._text(slide, s["subtext"], 0.9, 5.1, 11.5, 1.2, size=24, color=self.theme.muted)
        return slide

    def bullets(self, s):
        slide = self._slide()
        self._title(slide, s.get("title", ""))
        items = s.get("bullets", [])
        y = 2.1
        for item in items[:6]:
            self._rect(slide, 0.85, y + 0.17, 0.14, 0.14, self.theme.accent)
            self._text(slide, item, 1.2, y, 11.2, 0.9, size=26)
            y += 1.05
        return slide

    def image(self, s):
        slide = self._slide()
        self._title(slide, s.get("title", ""))
        bottom = 0.9 if s.get("caption") else 0.55
        self._image(slide, s.get("image"), 0.75, 1.85, self.W - 1.5, self.H - 1.85 - bottom,
                    label=s.get("title", "image"))  # fmt: skip
        if s.get("caption"):
            self._text(slide, s["caption"], 0.75, self.H - 0.95, self.W - 1.5, 0.5, size=16,
                       color=self.theme.muted, align="center")  # fmt: skip
        return slide

    def split(self, s):
        slide = self._slide()
        self._title(slide, s.get("title", ""))
        y = 2.1
        for item in s.get("bullets", [])[:5]:
            self._rect(slide, 0.85, y + 0.15, 0.13, 0.13, self.theme.accent)
            self._text(slide, item, 1.15, y, 4.9, 1.0, size=22)
            y += 1.1
        self._image(slide, s.get("image"), 6.4, 1.85, 6.2, 5.0, label=s.get("title", "split"))
        return slide

    def metrics(self, s):
        slide = self._slide()
        self._title(slide, s.get("title", ""))
        items = s.get("metrics", [])[:4]
        n = max(len(items), 1)
        gap = 0.35
        w = (self.W - 1.5 - gap * (n - 1)) / n
        for i, m in enumerate(items):
            x = 0.75 + i * (w + gap)
            color = self.theme.demo if m.get("demo") else self.theme.accent
            self._rect(slide, x, 2.3, w, 3.2, self.theme.surface)
            self._rect(slide, x, 2.3, 0.08, 3.2, color, radius=False)
            self._text(slide, m.get("value", ""), x + 0.35, 2.65, w - 0.5, 1.3, size=54, bold=True,
                       color=self.theme.demo if m.get("demo") else self.theme.text)  # fmt: skip
            self._text(slide, m.get("label", ""), x + 0.35, 3.95, w - 0.5, 0.7, size=20, bold=True)
            note = m.get("note", "") + ("  (DEMO value)" if m.get("demo") else "")
            if note.strip():
                self._text(slide, note.strip(), x + 0.35, 4.6, w - 0.5, 0.8, size=14,
                           color=self.theme.muted)  # fmt: skip
        if s.get("source"):
            self._text(slide, s["source"], 0.75, 5.85, self.W - 1.5, 0.5, size=14,
                       color=self.theme.muted)  # fmt: skip
        return slide

    def steps(self, s):
        slide = self._slide()
        self._title(slide, s.get("title", ""))
        items = s.get("steps", [])[:4]
        n = max(len(items), 1)
        gap = 0.35
        w = (self.W - 1.5 - gap * (n - 1)) / n
        for i, step in enumerate(items):
            x = 0.75 + i * (w + gap)
            self._rect(slide, x, 2.3, w, 3.6, self.theme.surface)
            self._rect(slide, x, 2.3, w, 0.08, self.theme.accent, radius=False)
            self._text(slide, str(i + 1), x + 0.35, 2.6, 1, 0.8, size=40, bold=True,
                       color=self.theme.accent)  # fmt: skip
            self._text(
                slide, step.get("title", ""), x + 0.35, 3.45, w - 0.6, 0.9, size=22, bold=True
            )
            self._text(slide, step.get("text", ""), x + 0.35, 4.3, w - 0.6, 1.5, size=16,
                       color=self.theme.muted)  # fmt: skip
        if s.get("footnote"):
            self._text(slide, s["footnote"], 0.75, 6.2, self.W - 1.5, 0.5, size=14,
                       color=self.theme.muted)  # fmt: skip
        return slide

    def divider(self, s):
        slide = self._slide("#000000")
        self._text(slide, s.get("text", "Live demo"), 0, 2.9, self.W, 1.6, size=72, bold=True,
                   align="center", anchor="middle")  # fmt: skip
        if s.get("subtext"):
            self._text(slide, s["subtext"], 0, 4.5, self.W, 0.8, size=22, color=self.theme.muted,
                       align="center")  # fmt: skip
        return slide

    def closing(self, s):
        slide = self._slide()
        self._text(slide, s.get("ask", ""), 0.9, 1.8, 11.5, 2.2, size=44, bold=True,
                   line_spacing=1.05)  # fmt: skip
        y = 4.3
        for link in s.get("links", [])[:4]:
            self._text(slide, link, 0.9, y, 11.5, 0.5, size=20, color=self.theme.accent)
            y += 0.55
        self._text(slide, s.get("thanks", "Thank you"), 0.9, 6.4, 11.5, 0.6, size=20,
                   color=self.theme.muted)  # fmt: skip
        return slide

    # ------------------------------------------------------------------ driver
    def add(self, number: int, s: dict[str, Any]) -> None:
        kind = s.get("kind", "bullets")
        maker = getattr(self, kind, None)
        if maker is None or kind.startswith("_") or kind in {"add", "save"}:
            raise SystemExit(f"slide {number}: unknown kind {kind!r}")
        label = f"slide {number} ({kind})"
        title = s.get("title", "")
        if len(title) > MAX_TITLE_CHARS:
            self.report.warnings.append(
                f"{label}: title is {len(title)} chars (max {MAX_TITLE_CHARS})"
            )
        visible = {
            k: v for k, v in s.items() if k not in {"notes", "kind", "image", "seconds", "rubric"}
        }
        count = words(visible)
        if count > MAX_WORDS and kind not in {"title", "closing"}:
            self.report.warnings.append(
                f"{label}: {count} words on the slide (aim for < {MAX_WORDS})"
            )
        if len(s.get("bullets", [])) > MAX_BULLETS:
            self.report.warnings.append(f"{label}: {len(s['bullets'])} bullets (max {MAX_BULLETS})")
        if not s.get("notes"):
            self.report.warnings.append(f"{label}: no speaker notes")
        if "seconds" not in s:
            self.report.warnings.append(f"{label}: no `seconds`, so the timing check ignores it")
        self.report.seconds += float(s.get("seconds", 0))
        slide = maker(s)
        if kind not in {"title", "divider"}:
            self._chrome(slide, number)
        if s.get("notes"):
            slide.notes_slide.notes_text_frame.text = s["notes"]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(path))


def _set_alpha(shape, alpha: float) -> None:
    """python-pptx has no API for fill transparency; set it in the XML."""
    from pptx.oxml.ns import qn

    solid = shape.fill._xPr.find(qn("a:solidFill"))
    if solid is None:
        return
    color = solid[0]
    for old in color.findall(qn("a:alpha")):
        color.remove(old)
    node = color.makeelement(qn("a:alpha"), {"val": str(int(alpha * 100000))})
    color.append(node)


def load_theme(deck: dict[str, Any]) -> Theme:
    theme = Theme()
    web_config = ROOT / "web" / "config.json"
    if web_config.exists():
        try:
            accent = json.loads(web_config.read_text(encoding="utf-8")).get("accent")
            if accent:
                theme.accent = accent
        except json.JSONDecodeError:
            pass
    for key, value in deck.get("theme", {}).items():
        if hasattr(theme, key):
            setattr(theme, key, value)
    return theme


def export_pdf(pptx: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)],
        capture_output=True,
        check=False,
        timeout=180,
    )
    pdf = pptx.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def previews(pdf: Path) -> Path | None:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return None
    folder = pdf.parent / f"{pdf.stem}-preview"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    subprocess.run([pdftoppm, "-png", "-r", "60", str(pdf), str(folder / "slide")], check=False)
    return folder


def build(config: Path, out: Path) -> tuple[Path, Report]:
    deck = tomllib.loads(config.read_text(encoding="utf-8"))
    meta = deck.get("deck", {})
    builder = DeckBuilder(load_theme(deck), config.parent, footer=meta.get("footer", ""))
    slides = deck.get("slide", [])
    if not slides:
        raise SystemExit(f"No [[slide]] in {config}")
    for number, slide in enumerate(slides, start=1):
        builder.add(number, slide)
    minutes = float(meta.get("minutes", 4))
    if builder.report.seconds > minutes * 60:
        builder.report.warnings.append(
            f"slides add up to {builder.report.seconds:.0f}s but the slot is {minutes:g} min"
        )
    path = out / f"{meta.get('name', 'deck')}.pptx"
    builder.save(path)
    return path, builder.report


def _rel(path: Path) -> Path:
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the pitch deck from docs/pitch/deck.toml.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args(argv)
    try:
        import pptx  # noqa: F401
    except ImportError:
        print('python-pptx missing: pip install -e ".[pitch]"')
        return 2
    path, report = build(args.config, args.out)
    print(f"  wrote {_rel(path)}")
    print(f"  timing: {report.seconds:.0f}s of speaking time in the slides")
    if not args.no_pdf:
        pdf = export_pdf(path)
        if pdf:
            print(f"  wrote {_rel(pdf)}")
            folder = previews(pdf)
            if folder:
                print(f"  previews in {_rel(folder)}/")
        else:
            print("  PDF skipped: install LibreOffice (soffice) or export from PowerPoint/Keynote")
    for warning in report.warnings:
        print(f"  WARN {warning}")
    print(f"deck: {len(report.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
