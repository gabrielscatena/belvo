"""Optional design PDF build: install reportlab; core engine does not depend on it."""

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ArchitectureDiagram(Flowable):
    """Compact code-native view of the implemented online and offline paths."""

    def __init__(self, width=A4[0] - 88):
        super().__init__()
        self.requested_width = width
        self.width, self.height = width, 85

    def wrap(self, available_width, available_height):
        self.width = min(self.requested_width, available_width)
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        ink = colors.HexColor("#163b59")
        muted = colors.HexColor("#53657a")
        gap, bottom, box_height = 18, 39, 31
        box_width = (self.width - 3 * gap) / 4
        labels = [
            ("Receiver", "validator"),
            ("Planner", "scorer"),
            ("SQLite state", "outbox"),
            ("Simulator", "executor"),
        ]
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(
            (3 * box_width + 2 * gap) / 2,
            77,
            "Synchronous planning and atomic commit",
        )
        canvas.drawCentredString(3 * (box_width + gap) + box_width / 2, 77, "Asynchronous dispatch")
        for index, (title, subtitle) in enumerate(labels):
            left = index * (box_width + gap)
            canvas.setFillColor(colors.HexColor("#e8eff5"))
            canvas.setStrokeColor(colors.HexColor("#a8b9c7"))
            canvas.setLineWidth(0.7)
            canvas.roundRect(left, bottom, box_width, box_height, 4, fill=1, stroke=1)
            canvas.setFillColor(ink)
            canvas.setFont("Helvetica-Bold", 8.2)
            canvas.drawCentredString(left + box_width / 2, bottom + 19, title)
            canvas.setFont("Helvetica", 8.1)
            canvas.drawCentredString(left + box_width / 2, bottom + 8, subtitle)
            if index == len(labels) - 1:
                continue
            start, end = left + box_width + 2, left + box_width + gap - 2
            middle = bottom + box_height / 2
            canvas.setStrokeColor(ink)
            canvas.setFillColor(ink)
            canvas.setDash(2, 2) if index == 2 else canvas.setDash()
            canvas.line(start, middle, end - 3, middle)
            canvas.setDash()
            arrow = canvas.beginPath()
            arrow.moveTo(end, middle)
            arrow.lineTo(end - 4, middle + 2.5)
            arrow.lineTo(end - 4, middle - 2.5)
            arrow.close()
            canvas.drawPath(arrow, fill=1, stroke=0)
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(
            self.width / 2,
            14,
            "Offline: CSV history -> fitting / reporting; runtime outcomes feedback not implemented.",
        )
        canvas.restoreState()


def inline(text):
    text = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "output/pdf/design_document.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.4,
            textColor=colors.HexColor("#223044"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle("Cell", parent=styles["Body"], fontSize=8.7, leading=11.5, spaceAfter=0)
    )
    styles["Title"].textColor = colors.HexColor("#163b59")
    styles["Title"].fontSize = 24
    styles["Title"].leading = 28
    styles["Title"].spaceAfter = 10
    styles["Heading2"].fontSize = 12.5
    styles["Heading2"].leading = 16
    styles["Heading2"].textColor = colors.HexColor("#163b59")
    styles["Heading2"].spaceBefore = 10
    styles["Heading2"].spaceAfter = 8
    story, paragraph, table = [], [], []

    def flush():
        if paragraph:
            story.append(Paragraph(inline(" ".join(paragraph)), styles["Body"]))
            paragraph.clear()
        if table:
            rows = [[Paragraph(inline(cell), styles["Cell"]) for cell in row] for row in table]
            width = A4[0] - 88
            widths = (
                [width * 0.28, width * 0.72]
                if table[0][0] == "Component"
                else [width * 0.76, width * 0.24]
            )
            grid = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            grid.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eff5")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#a8b9c7")),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f5f7fa")],
                        ),
                    ]
                )
            )
            story.extend([grid, Spacer(1, 10)])
            table.clear()

    for line in (root / "docs/design_document.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("|---"):
            continue
        if line.startswith("|"):
            if paragraph:
                flush()
            table.append([cell.strip() for cell in line.strip("|").split("|")])
        elif not line:
            flush()
        elif line == "<!-- PAGEBREAK -->":
            flush()
            story.append(PageBreak())
        elif line == "<!-- ARCHITECTURE -->":
            flush()
            story.append(ArchitectureDiagram())
        elif line.startswith("# "):
            flush()
            story.append(Paragraph(inline(line[2:]), styles["Title"]))
        elif line.startswith("## "):
            flush()
            story.append(Paragraph(inline(line[3:]), styles["Heading2"]))
        else:
            paragraph.append(line)
    flush()

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#d3dde5"))
        canvas.line(44, 35, A4[0] - 44, 35)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#53657a"))
        canvas.drawString(44, 23, "Belvo | Smart Collections Engine | 29 Oct 2026")
        canvas.drawRightString(A4[0] - 44, 23, f"Page {doc.page}")

    SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=38,
        bottomMargin=46,
        title="Smart Collections Engine - Design",
        author="Gabriel Scatena",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    print(target)


if __name__ == "__main__":
    main()
