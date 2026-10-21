"""Render the source SVG into a window icon and a Windows multi-size ICO."""

import os
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> None:
    app = QGuiApplication([])
    directory = Path(__file__).resolve().parent
    renderer = QSvgRenderer(str(directory / "icon.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid icon.svg")

    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        images.append((size, bytes(data)))

    (directory / "icon.png").write_bytes(images[-1][1])
    offset = 6 + 16 * len(images)
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = []
    for size, data in images:
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (directory / "icon.ico").write_bytes(header + b"".join(entries) + b"".join(data for _, data in images))
    app.quit()


if __name__ == "__main__":
    main()
