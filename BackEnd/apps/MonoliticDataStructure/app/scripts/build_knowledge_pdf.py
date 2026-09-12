"""Crea un PDF portable a partir de la fuente de conocimiento de Proyecto Jupiter."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "knowledge" / "proyecto_jupiter_conocimiento.md"
TARGET = ROOT / "data" / "knowledge" / "guia_conocimiento_proyecto_jupiter.pdf"
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LINES_PER_PAGE = 47


def clean_line(line: str) -> str:
    text = line.replace("#", "").replace("`", "").strip()
    return text.encode("ascii", "ignore").decode("ascii")


def wrap_line(line: str, width: int = 92) -> list[str]:
    words = line.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + ([current] if current else [])


def document_lines() -> list[str]:
    lines: list[str] = []
    for raw_line in SOURCE.read_text(encoding="utf-8").splitlines():
        cleaned = clean_line(raw_line)
        lines.extend(wrap_line(cleaned) if cleaned else [""])
    return lines


def escape_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "50 750 Td", "12 TL"]
    for line in lines:
        commands.append(f"({escape_pdf(line)}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def build_pdf(lines: list[str]) -> bytes:
    pages = [lines[index : index + LINES_PER_PAGE] for index in range(0, len(lines), LINES_PER_PAGE)]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids = []
    for page in pages:
        stream = page_stream(page)
        content_id = len(objects) + 2
        page_ids.append(len(objects) + 1)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects[1] = b"<< /Type /Pages /Kids [" + b" ".join(f"{item} 0 R".encode() for item in page_ids) + b"] /Count " + str(len(page_ids)).encode() + b" >>"
    return serialize_pdf(objects)


def serialize_pdf(objects: list[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def main() -> None:
    TARGET.write_bytes(build_pdf(document_lines()))
    print(f"PDF creado: {TARGET}")


if __name__ == "__main__":
    main()
