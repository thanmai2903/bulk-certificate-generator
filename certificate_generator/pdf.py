"""The single, predefined PDF certificate design."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


def _font() -> str:
    # ReportLab ships this font, so the project needs no system font installation.
    font_path = Path(__import__("reportlab").__file__).parent / "fonts" / "Vera.ttf"
    if "CertificateVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CertificateVera", str(font_path)))
    return "CertificateVera"


def _wrap(text: str, font: str, size: int, max_width: float) -> list[str]:
    """Wrap even unusually long words without drawing outside the border."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        for char in word:
            if line and pdfmetrics.stringWidth(line + char, font, size) > max_width:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines


def generate_pdf(path: Path, *, name: str, email: str, course: str,
                 issue_date: str, recipient_id: str | None = None) -> None:
    """Create one certificate. The caller provides a unique, safe file path."""
    font = _font()
    width, height = landscape(A4)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(path), pagesize=(width, height))
    canvas.setTitle(f"Certificate - {name}")
    canvas.setFillColor(colors.HexColor("#F8F5EE"))
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor("#153D43"))
    canvas.setLineWidth(3)
    canvas.rect(28, 28, width - 56, height - 56, fill=0, stroke=1)
    canvas.setLineWidth(0.8)
    canvas.rect(37, 37, width - 74, height - 74, fill=0, stroke=1)
    canvas.setFillColor(colors.HexColor("#153D43"))
    canvas.setFont(font, 16)
    canvas.drawCentredString(width / 2, height - 115, "CERTIFICATE OF COMPLETION")
    canvas.setFillColor(colors.HexColor("#596568"))
    canvas.setFont(font, 13)
    canvas.drawCentredString(width / 2, height - 163, "Presented to")
    canvas.setFillColor(colors.HexColor("#153D43"))
    name_size = 30 if len(name) <= 60 else 16
    name_lines = _wrap(name, font, name_size, width - 120)
    canvas.setFont(font, name_size)
    for index, line in enumerate(name_lines):
        canvas.drawCentredString(width / 2, height - 205 - index * (name_size + 5), line)
    divider_y = height - 224 - (len(name_lines) - 1) * (name_size + 5)
    canvas.setStrokeColor(colors.HexColor("#B89B5E"))
    canvas.line(width / 2 - 150, divider_y, width / 2 + 150, divider_y)
    canvas.setFillColor(colors.HexColor("#596568"))
    canvas.setFont(font, 12)
    canvas.drawCentredString(width / 2, divider_y - 35, "For successfully completing")
    canvas.setFillColor(colors.HexColor("#153D43"))
    course_size = 20 if len(course) <= 80 else 15
    canvas.setFont(font, course_size)
    for index, line in enumerate(_wrap(course, font, course_size, width - 120)):
        canvas.drawCentredString(width / 2, divider_y - 73 - index * (course_size + 5), line)
    canvas.setFont(font, 10)
    canvas.drawCentredString(width / 2, 105, f"Issued {issue_date}  |  {email}")
    if recipient_id:
        canvas.drawCentredString(width / 2, 83, f"Recipient ID: {recipient_id}")
    canvas.save()

