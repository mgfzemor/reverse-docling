"""Simulate bad scans / phone photos on page images.

Each preset maps an effect name to the (min, max) range its strength is sampled from per page, and the
probability that the effect is applied at all. The sampled parameters are returned so they can be
recorded in the manifest.
"""

from __future__ import annotations

import random
from typing import Any

import cv2
import numpy as np

# effect -> (probability, (min, max))
PRESETS: dict[str, dict[str, tuple[float, tuple[float, float]]]] = {
    "none": {},
    "light": {
        "rotation": (0.7, (-1.0, 1.0)),          # degrees
        "gaussian_blur": (0.4, (0.3, 0.8)),      # sigma
        "gaussian_noise": (0.5, (2, 6)),         # std in intensity levels
        "brightness": (0.4, (-12, 12)),
        "contrast": (0.4, (0.9, 1.1)),
        "jpeg_quality": (0.5, (70, 90)),
    },
    "medium": {
        "rotation": (0.9, (-2.5, 2.5)),
        "perspective": (0.4, (0.005, 0.02)),     # corner jitter as fraction of size
        "gaussian_blur": (0.6, (0.6, 1.3)),
        "motion_blur": (0.2, (3, 7)),            # kernel length
        "gaussian_noise": (0.7, (5, 12)),
        "salt_pepper": (0.3, (0.0005, 0.002)),
        "brightness": (0.6, (-25, 20)),
        "contrast": (0.6, (0.8, 1.15)),
        "downscale": (0.4, (0.5, 0.8)),          # resample factor
        "paper_tint": (0.5, (0.02, 0.08)),
        "shadow": (0.3, (0.1, 0.3)),
        "jpeg_quality": (0.7, (45, 75)),
        "grayscale": (0.3, (1, 1)),
    },
    "heavy": {
        "rotation": (1.0, (-5.0, 5.0)),
        "perspective": (0.7, (0.01, 0.045)),
        "gaussian_blur": (0.7, (0.8, 1.6)),
        "motion_blur": (0.3, (3, 7)),
        "gaussian_noise": (0.9, (8, 18)),
        "salt_pepper": (0.6, (0.002, 0.008)),
        "brightness": (0.8, (-45, 30)),
        "contrast": (0.8, (0.6, 1.25)),
        "downscale": (0.7, (0.4, 0.65)),
        "paper_tint": (0.7, (0.05, 0.15)),
        "shadow": (0.6, (0.2, 0.5)),
        "fold": (0.4, (1, 2)),                   # number of fold lines
        "jpeg_quality": (0.9, (20, 50)),
        "grayscale": (0.5, (1, 1)),
        "binarize": (0.1, (1, 1)),
    },
}

_INT_EFFECTS = {"motion_blur", "jpeg_quality", "fold", "grayscale", "binarize"}
# Fixed application order: geometry, then optics, then sensor/compression artefacts.
_ORDER = ["paper_tint", "fold", "shadow", "rotation", "perspective", "downscale", "gaussian_blur", "motion_blur",
          "brightness", "contrast", "gaussian_noise", "salt_pepper", "grayscale", "binarize", "jpeg_quality"]


def sample_params(preset: str, rng: random.Random,
                  overrides: dict[str, tuple[float, float]] | None = None) -> dict[str, float]:
    spec = dict(PRESETS[preset])
    for name, rng_range in (overrides or {}).items():
        spec[name] = (1.0, tuple(rng_range))  # explicit overrides are always applied
    params: dict[str, float] = {}
    for name in _ORDER:
        if name not in spec:
            continue
        prob, (lo, hi) = spec[name]
        if rng.random() < prob:
            value = rng.uniform(lo, hi)
            params[name] = int(round(value)) if name in _INT_EFFECTS else round(value, 4)
    return params


def apply(img: np.ndarray, params: dict[str, float], rng: random.Random) -> np.ndarray:
    nrng = np.random.default_rng(rng.randrange(2**32))
    out = img.copy()
    h, w = out.shape[:2]
    # Blur strengths are defined for a ~150 DPI page (1240 px wide); scale them to the actual resolution.
    res = max(min(h, w) / 1240, 0.3)
    bg = (255, 255, 255)
    for name in _ORDER:
        if name not in params:
            continue
        v = params[name]
        if name == "paper_tint":
            tint = np.array([1 - v * 1.6, 1 - v * 0.6, 1.0])  # warm/yellowish paper (BGR)
            out = np.clip(out.astype(np.float32) * tint, 0, 255).astype(np.uint8)
        elif name == "fold":
            for _ in range(int(v)):
                out = _fold_line(out, nrng)
        elif name == "shadow":
            out = _edge_shadow(out, v, nrng)
        elif name == "rotation":
            m = cv2.getRotationMatrix2D((w / 2, h / 2), v, 1.0)
            out = cv2.warpAffine(out, m, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=bg,
                                 flags=cv2.INTER_LINEAR)
        elif name == "perspective":
            src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
            jitter = nrng.uniform(-v, v, size=(4, 2)) * [w, h]
            m = cv2.getPerspectiveTransform(src, (src + jitter).astype(np.float32))
            out = cv2.warpPerspective(out, m, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=bg)
        elif name == "downscale":
            small = cv2.resize(out, (max(1, int(w * v)), max(1, int(h * v))), interpolation=cv2.INTER_AREA)
            out = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
        elif name == "gaussian_blur":
            out = cv2.GaussianBlur(out, (0, 0), sigmaX=v * res)
        elif name == "motion_blur":
            k = max(3, int(v * res) | 1)
            kernel = np.zeros((k, k), np.float32)
            kernel[k // 2, :] = 1.0 / k
            angle = nrng.uniform(0, 180)
            kernel = cv2.warpAffine(kernel, cv2.getRotationMatrix2D((k / 2 - .5, k / 2 - .5), angle, 1.0), (k, k))
            out = cv2.filter2D(out, -1, kernel / max(kernel.sum(), 1e-6))
        elif name == "brightness":
            out = cv2.convertScaleAbs(out, alpha=1.0, beta=v)
        elif name == "contrast":
            out = cv2.convertScaleAbs(out, alpha=v, beta=128 * (1 - v))
        elif name == "gaussian_noise":
            noise = nrng.normal(0, v, out.shape)
            out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        elif name == "salt_pepper":
            mask = nrng.random(out.shape[:2])
            out[mask < v / 2] = 0
            out[mask > 1 - v / 2] = 255
        elif name == "grayscale":
            out = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        elif name == "binarize":
            gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
            out = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        elif name == "jpeg_quality":
            ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, int(v)])
            out = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return out


def _fold_line(img: np.ndarray, nrng: np.random.Generator) -> np.ndarray:
    h, w = img.shape[:2]
    out = img.astype(np.float32)
    horizontal = nrng.random() < 0.7
    pos = int(nrng.uniform(0.25, 0.75) * (h if horizontal else w))
    width = max(3, int(min(h, w) * 0.006))
    profile = np.exp(-np.linspace(-2, 2, 2 * width) ** 2)  # dark crease with soft falloff
    for i, p in enumerate(profile):
        idx = pos - width + i
        if horizontal and 0 <= idx < h:
            out[idx, :, :] *= 1 - 0.25 * p
        elif not horizontal and 0 <= idx < w:
            out[:, idx, :] *= 1 - 0.25 * p
    return np.clip(out, 0, 255).astype(np.uint8)


def _edge_shadow(img: np.ndarray, strength: float, nrng: np.random.Generator) -> np.ndarray:
    """Darken one side of the page with a gradient, like a phone photo or book gutter."""
    h, w = img.shape[:2]
    side = nrng.integers(4)
    ramp = np.linspace(1 - strength, 1, w if side < 2 else h, dtype=np.float32)
    ramp = ramp if side % 2 == 0 else ramp[::-1]
    mask = np.tile(ramp, (h, 1)) if side < 2 else np.tile(ramp[:, None], (1, w))
    return np.clip(img.astype(np.float32) * mask[..., None], 0, 255).astype(np.uint8)


def degrade_pages(pages: list[np.ndarray], preset: str, rng: random.Random,
                  overrides: dict[str, tuple[float, float]] | None = None) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    out, used = [], []
    for page in pages:
        params = sample_params(preset, rng, overrides)
        out.append(apply(page, params, rng))
        used.append(params)
    return out, used
