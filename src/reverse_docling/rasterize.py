"""PDF <-> page images, via PyMuPDF (no poppler needed)."""

from __future__ import annotations

import cv2
import numpy as np
import pymupdf


def pdf_to_images(pdf: bytes, dpi: int = 150) -> list[np.ndarray]:
    """Return one BGR uint8 array per page."""
    pages = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            pages.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return pages


def encode_image(img: np.ndarray, fmt: str = "png", jpeg_quality: int = 92) -> bytes:
    params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality] if fmt == "jpg" else []
    ok, buf = cv2.imencode(f".{fmt}", img, params)
    if not ok:
        raise RuntimeError(f"Could not encode image as {fmt}")
    return buf.tobytes()


def images_to_pdf(images: list[np.ndarray], dpi: int = 150) -> bytes:
    """Build an image-only PDF (like a scanner would), page size derived from DPI."""
    out = pymupdf.open()
    for img in images:
        h, w = img.shape[:2]
        page = out.new_page(width=w * 72 / dpi, height=h * 72 / dpi)
        page.insert_image(page.rect, stream=encode_image(img, "jpg", 88))
    data = out.tobytes(deflate=True)
    out.close()
    return data


def page_count(pdf: bytes) -> int:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return doc.page_count
