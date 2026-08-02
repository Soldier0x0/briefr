#!/usr/bin/env python3
"""Generate BRIEFR marketing reels — distinct cuts, motion graphics, brand lockup.

Outputs silent 1080×1920 MP4s to docs/marketing/reels/.
Pair with docs/marketing/reel-f5-tts-speak-only.txt for F5 TTS voiceover.

Requires: Pillow, ffmpeg.
Optional: Playwright screenshots in docs/marketing/screenshots/ (run capture_screenshots.py).
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "docs" / "marketing" / "brand"
SHOT_DIR = ROOT / "docs" / "marketing" / "screenshots"
OUT_DIR = ROOT / "docs" / "marketing" / "reels"

FPS = 30
W, H = 1080, 1920
SAFE = 900
X0 = (W - SAFE) // 2

BG = (10, 10, 8)
SURFACE = (17, 17, 16)
CARD = (18, 18, 17)
LINE = (42, 42, 37)
TEXT = (232, 230, 223)
MUTED = (167, 163, 150)
FAINT = (108, 106, 98)
ACCENT = (232, 85, 51)
GREEN = (74, 158, 106)
AMBER = (212, 134, 10)

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - math.cos(t * math.pi) / 2


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def alpha_color(rgb: tuple[int, int, int], a: float) -> tuple[int, int, int]:
    return tuple(int(c * a) for c in rgb)


def new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def load_shot(name: str) -> Image.Image | None:
    path = SHOT_DIR / name
    if not path.exists():
        return None
    img = Image.open(path).convert("RGB")
    return img.resize((W, H), Image.Resampling.LANCZOS)


def load_logo(variant: str = "primary") -> Image.Image | None:
    for name in (f"{variant}-logo.png", "primary-logo.png", "mark.png"):
        p = BRAND_DIR / name
        if p.exists():
            return Image.open(p).convert("RGBA")
    svg = BRAND_DIR / f"{variant}-logo.svg"
    if not svg.exists():
        svg = BRAND_DIR / "primary-logo.svg"
    if svg.exists():
        try:
            import cairosvg  # type: ignore

            png = BRAND_DIR / f"{variant}-logo-raster.png"
            cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=1200)
            return Image.open(png).convert("RGBA")
        except Exception:
            pass
    return None


def draw_brand_lockup(draw: ImageDraw.ImageDraw, img: Image.Image, cy: int, a: float = 1.0, dy: int = 0, scale: float = 0.85) -> None:
    logo = load_logo("primary")
    if logo and a > 0:
        paste_center(img, logo, cy + dy - 30, scale=scale, a=a)
        return
    draw_wordmark(draw, cy, a, dy)


def paste_center(img: Image.Image, overlay: Image.Image, y: int, scale: float = 1.0, a: float = 1.0) -> None:
    ow, oh = overlay.size
    nw, nh = int(ow * scale), int(oh * scale)
    o = overlay.resize((nw, nh), Image.Resampling.LANCZOS)
    if a < 1.0:
        o = o.copy()
        alpha = o.split()[3]
        alpha = alpha.point(lambda p: int(p * a))
        o.putalpha(alpha)
    x = (W - nw) // 2
    img.paste(o, (x, y), o)


def draw_logo_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float, progress: float = 1.0) -> None:
    """Animate logo bars drawing in (0→1)."""
    s = scale
    # vertical bars
    if progress > 0.05:
        a = ease_out(min(1.0, (progress - 0.05) / 0.15))
        draw.rounded_rectangle(
            (cx - 28 * s, cy - 36 * s, cx - 22 * s, cy + 36 * s),
            radius=int(2 * s),
            fill=alpha_color(FAINT, a),
        )
        draw.rounded_rectangle(
            (cx - 16 * s, cy - 36 * s, cx - 10 * s, cy + 36 * s),
            radius=int(2 * s),
            fill=alpha_color(FAINT, a),
        )
    bars = [
        (0.2, ACCENT, 44 * s, 6 * s),
        (0.4, TEXT, 30 * s, 5 * s),
        (0.6, MUTED, 20 * s, 5 * s),
    ]
    bx = cx + 4 * s
    for start, color, bw, bh in bars:
        if progress < start:
            continue
        a = ease_out(min(1.0, (progress - start) / 0.2))
        w = bw * a
        draw.rounded_rectangle((bx, cy - 28 * s, bx + w, cy - 28 * s + bh), radius=2, fill=alpha_color(color, a))
        draw.rounded_rectangle((bx, cy - 6 * s, bx + w * 0.7, cy - 6 * s + bh), radius=2, fill=alpha_color(color, a * 0.85))
        draw.rounded_rectangle((bx, cy + 16 * s, bx + w * 0.45, cy + 16 * s + bh), radius=2, fill=alpha_color(color, a * 0.7))


def draw_wordmark(draw: ImageDraw.ImageDraw, cy: int, a: float = 1.0, dy: int = 0) -> None:
    draw_logo_mark(draw, W // 2 - 80, cy + dy, 1.4, a)
    serif = _font(FONT_SERIF, 58)
    text = "BRIEFR"
    tw = draw.textlength(text, font=serif)
    draw.text((W // 2 - tw / 2 + 40, cy - 20 + dy), text, font=serif, fill=alpha_color(TEXT, a))


def text_center(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont, fill=TEXT, a: float = 1.0, dy: int = 0) -> None:
    tw = draw.textlength(text, font=font)
    draw.text(((W - tw) / 2, y + dy), text, font=font, fill=alpha_color(fill, a))


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw_dummy_length(test, font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_dummy_length(text: str, font: ImageFont.FreeTypeFont) -> float:
    return font.getlength(text)


def card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, a: float = 1.0, accent: bool = False) -> None:
    fill = alpha_color(CARD, a)
    border = alpha_color(LINE, a)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=fill, outline=border)
    if accent:
        draw.rectangle((x, y + 8, x + 4, y + h - 8), fill=alpha_color(ACCENT, a))


def mock_morning_brief(draw: ImageDraw.ImageDraw, a: float, dy: int = 0) -> None:
    y = 180 + dy
    mono = _font(FONT_MONO, 22)
    sans_b = _font(FONT_SANS_BOLD, 28)
    text_center(draw, y, "// MORNING BRIEF", sans_b, ACCENT, a)
    y += 50
    card(draw, X0, y, SAFE, 120, a, True)
    draw.text((X0 + 24, y + 20), "Last 24 hours · ranked action queue", font=mono, fill=alpha_color(MUTED, a))
    items = [
        ("KEV due in 3 days", "CVE-2025-24813", "CRITICAL"),
        ("EPSS +18%", "CVE-2024-3400", "CRITICAL"),
        ("Stack match", "CVE-2023-4966", "HIGH"),
    ]
    iy = y + 52
    for label, cve, sev in items:
        draw.text((X0 + 24, iy), f"{label}  ·  {cve}", font=mono, fill=alpha_color(TEXT, a))
        draw.text((X0 + SAFE - 120, iy), sev, font=mono, fill=alpha_color(ACCENT if sev == "CRITICAL" else AMBER, a))
        iy += 22


def mock_cve_detail(draw: ImageDraw.ImageDraw, a: float, dy: int = 0, scroll: float = 0.0) -> None:
    y = 140 + dy - int(scroll * 120)
    mono = _font(FONT_MONO, 20)
    sans_b = _font(FONT_SANS_BOLD, 30)
    draw.text((X0, y), "CVE-2025-24813", font=sans_b, fill=alpha_color(TEXT, a))
    y += 44
    card(draw, X0, y, SAFE, 100, a, True)
    draw.text((X0 + 20, y + 16), "Risk Score", font=mono, fill=alpha_color(MUTED, a))
    draw.text((X0 + 20, y + 44), "87", font=_font(FONT_SERIF, 52), fill=alpha_color(ACCENT, a))
    draw.text((X0 + 100, y + 50), "Stack match · KEV · EPSS rising", font=mono, fill=alpha_color(MUTED, a))
    y += 120
    card(draw, X0, y, SAFE, 130, a)
    draw.text((X0 + 20, y + 16), "REMEDIATION", font=mono, fill=alpha_color(ACCENT, a))
    draw.text((X0 + 20, y + 48), "PATCH AVAILABLE", font=_font(FONT_SANS_BOLD, 24), fill=alpha_color(GREEN, a))
    draw.text((X0 + 20, y + 82), "Upgrade Apache Tomcat to a fixed release.", font=mono, fill=alpha_color(TEXT, a))


def mock_ioc_graph(draw: ImageDraw.ImageDraw, progress: float, a: float = 1.0) -> None:
    mono = _font(FONT_MONO, 22)
    sans_b = _font(FONT_SANS_BOLD, 28)
    text_center(draw, 160, "IOC LOOKUP", sans_b, TEXT, a)
    text_center(draw, 200, "IP · hash · domain", mono, MUTED, a)
    cx, cy = W // 2, 520
    inputs = [("IP", cx - 220, cy - 180), ("HASH", cx, cy - 220), ("DOMAIN", cx + 180, cy - 180)]
    sources = [
        ("VirusTotal", cx - 200, cy + 120),
        ("AbuseIPDB", cx, cy + 200),
        ("GreyNoise", cx + 180, cy + 120),
        ("MalwareBazaar", cx - 100, cy + 280),
    ]
    # center node
    card(draw, cx - 70, cy - 30, 140, 60, a, True)
    draw.text((cx - 42, cy - 12), "IOC", font=mono, fill=alpha_color(TEXT, a))
    for i, (label, x, y) in enumerate(inputs):
        t = max(0.0, min(1.0, (progress - i * 0.12) / 0.25))
        if t <= 0:
            continue
        ta = ease_out(t) * a
        card(draw, x - 50, y - 22, 100, 44, ta)
        draw.text((x - 36, y - 10), label, font=mono, fill=alpha_color(TEXT, ta))
        draw.line((x, y + 22, cx, cy - 30), fill=alpha_color(ACCENT, ta * ease_out(t)), width=2)
    for i, (label, x, y) in enumerate(sources):
        t = max(0.0, min(1.0, (progress - 0.35 - i * 0.1) / 0.25))
        if t <= 0:
            continue
        ta = ease_out(t) * a
        card(draw, x - 72, y - 22, 144, 44, ta)
        draw.text((x - 60, y - 8), label, font=mono, fill=alpha_color(MUTED, ta))
        ex, ey = cx + (x - cx) * 0.35, cy + 30 + (y - cy) * 0.35
        draw.line((cx, cy + 30, ex, ey), fill=alpha_color(ACCENT, ta * 0.8), width=2)
        draw.line((ex, ey, x, y - 22), fill=alpha_color(ACCENT, ta * 0.8), width=2)


def mock_pdf_page(draw: ImageDraw.ImageDraw, a: float, scroll: float = 0.0) -> None:
    y0 = 120 - int(scroll * 400)
    mono = _font(FONT_MONO, 18)
    sans_b = _font(FONT_SANS_BOLD, 26)
    # full-page document mock
    card(draw, 60, y0, W - 120, H - 240, a)
    draw.text((90, y0 + 24), "BRIEFR", font=mono, fill=alpha_color(ACCENT, a))
    draw.text((90, y0 + 56), "CVE-2025-24813", font=_font(FONT_SERIF, 36), fill=alpha_color(TEXT, a))
    sections = [
        ("TRIAGE SNAPSHOT", "Critical · KEV · stack match · EPSS 72%"),
        ("EXECUTIVE SUMMARY", "Apache Tomcat path traversal with active exploitation signals."),
        ("WHY THIS MATTERS", "Public-facing Tomcat deployments in your stack are exposed."),
        ("TECHNICAL DETAIL", "Affected: tomcat. Patch available."),
        ("THREAT INTELLIGENCE", "CISA KEV · OTX pulses · ATT&CK T1190"),
        ("RECOMMENDED ACTIONS", "Patch · verify exposure · deploy detection rules"),
    ]
    y = y0 + 110
    for title, body in sections:
        draw.text((90, y), f"// {title}", font=mono, fill=alpha_color(ACCENT, a))
        for line in wrap_text(body, mono, W - 200):
            y += 22
            draw.text((90, y), line, font=mono, fill=alpha_color(TEXT, a))
        y += 36


def mock_feed_stack(draw: ImageDraw.ImageDraw, a: float) -> None:
    mono = _font(FONT_MONO, 20)
    sans_b = _font(FONT_SANS_BOLD, 28)
    text_center(draw, 150, "YOUR STACK · PRIORITIZED", sans_b, TEXT, a)
    chips = ["apache:tomcat", "paloaltonetworks:pan-os", "citrix:netscaler"]
    cx = X0
    for i, c in enumerate(chips):
        card(draw, cx + i * 10, 210 + i * 8, 280, 44, a)
        draw.text((cx + 16 + i * 10, 222 + i * 8), c, font=mono, fill=alpha_color(ACCENT, a))
    rows = [
        ("CVE-2025-24813", "87", "STACK MATCH"),
        ("CVE-2024-3400", "82", "KEV"),
        ("CVE-2023-4966", "76", "EPSS ↑"),
    ]
    y = 340
    for cve, score, tag in rows:
        card(draw, X0, y, SAFE, 72, a, tag == "STACK MATCH")
        draw.text((X0 + 20, y + 14), cve, font=mono, fill=alpha_color(TEXT, a))
        draw.text((X0 + SAFE - 180, y + 14), tag, font=mono, fill=alpha_color(ACCENT, a))
        draw.text((X0 + SAFE - 60, y + 10), score, font=_font(FONT_SERIF, 32), fill=alpha_color(ACCENT, a))
        y += 84


def mock_risk_bars(draw: ImageDraw.ImageDraw, progress: float, a: float = 1.0) -> None:
    mono = _font(FONT_MONO, 20)
    sans_b = _font(FONT_SANS_BOLD, 30)
    text_center(draw, 140, "EXPLAINABLE RISK SCORE", sans_b, TEXT, a)
    factors = [
        ("Asset match", 0.35),
        ("KEV listed", 0.25),
        ("EPSS", 0.15),
        ("Exploit available", 0.10),
        ("CVSS", 0.10),
        ("Momentum", 0.05),
    ]
    y = 240
    bar_w = SAFE - 80
    for i, (name, weight) in enumerate(factors):
        t = max(0.0, min(1.0, (progress - i * 0.1) / 0.2))
        if t <= 0:
            continue
        ta = ease_out(t) * a
        draw.text((X0, y), f"{name}  {weight:.2f}", font=mono, fill=alpha_color(TEXT, ta))
        bw = int(bar_w * weight * ta)
        draw.rounded_rectangle((X0, y + 28, X0 + bw, y + 40), radius=3, fill=alpha_color(ACCENT, ta))
        y += 64
    if progress > 0.75:
        sc = ease_out((progress - 0.75) / 0.25)
        draw.text((X0, y + 20), "Total", font=mono, fill=alpha_color(MUTED, a * sc))
        draw.text((X0 + 80, y + 8), "87", font=_font(FONT_SERIF, 56), fill=alpha_color(ACCENT, a * sc))


def mock_correlation(draw: ImageDraw.ImageDraw, progress: float, a: float = 1.0) -> None:
    sans_b = _font(FONT_SANS_BOLD, 30)
    mono = _font(FONT_MONO, 20)
    text_center(draw, 140, "CVE CORRELATION", sans_b, TEXT, a)
    nodes = [(W // 2, 420), (X0 + 80, 620), (X0 + SAFE - 80, 620), (W // 2, 780)]
    labels = ["CVE-A", "CVE-B", "CVE-C", "OTX pulse"]
    for i, ((x, y), label) in enumerate(zip(nodes, labels)):
        t = ease_out(min(1.0, max(0.0, (progress - i * 0.15) / 0.3)))
        card(draw, x - 60, y - 24, 120, 48, a * t, i == 0)
        draw.text((x - 40, y - 8), label, font=mono, fill=alpha_color(TEXT, a * t))
    pairs = [(0, 1), (0, 2), (0, 3), (1, 2)]
    for i, (a_idx, b_idx) in enumerate(pairs):
        t = ease_out(min(1.0, max(0.0, (progress - 0.35 - i * 0.08) / 0.2)))
        if t <= 0:
            continue
        x1, y1 = nodes[a_idx]
        x2, y2 = nodes[b_idx]
        draw.line((x1, y1, x2, y2), fill=alpha_color(ACCENT, a * t * 0.9), width=2)


def mock_data_hub(draw: ImageDraw.ImageDraw, progress: float, a: float = 1.0) -> None:
    sans_b = _font(FONT_SANS_BOLD, 30)
    mono = _font(FONT_MONO, 18)
    text_center(draw, 120, "DATA INGESTION", sans_b, TEXT, a)
    feeds = ["NVD", "KEV", "EPSS", "OTX", "ATT&CK", "ExploitDB", "OSV", "SigmaHQ"]
    cx, cy = W // 2, 520
    for i, name in enumerate(feeds):
        angle = -math.pi / 2 + i * (2 * math.pi / len(feeds))
        t = ease_out(min(1.0, max(0.0, (progress - i * 0.05) / 0.25)))
        fx = cx + int(math.cos(angle) * 280 * t)
        fy = cy + int(math.sin(angle) * 280 * t)
        card(draw, fx - 52, fy - 18, 104, 36, a * t)
        draw.text((fx - 40, fy - 8), name, font=mono, fill=alpha_color(TEXT, a * t))
        draw.line((fx, fy, cx, cy), fill=alpha_color(ACCENT, a * t * 0.7), width=2)
    if progress > 0.6:
        t = ease_out((progress - 0.6) / 0.3)
        card(draw, cx - 90, cy - 36, 180, 72, a * t, True)
        draw.text((cx - 72, cy - 18), "PostgreSQL 16", font=mono, fill=alpha_color(TEXT, a * t))
        draw.text((cx - 60, cy + 8), "+ pgvector", font=mono, fill=alpha_color(MUTED, a * t))


def mock_deploy(draw: ImageDraw.ImageDraw, a: float) -> None:
    mono = _font(FONT_MONO, 20)
    sans_b = _font(FONT_SANS_BOLD, 28)
    text_center(draw, 140, "SELF-HOST IN MINUTES", sans_b, TEXT, a)
    lines = [
        "docker compose -f deploy/docker-compose.postgres.yml up -d",
        "DATABASE_URL=postgresql://briefr:briefr@localhost:5432/briefr",
        "BRIEFR_REQUIRE_POSTGRES=1",
        "./scripts/verify-local.sh",
    ]
    y = 280
    card(draw, X0, y, SAFE, 320, a)
    for line in lines:
        for wrapped in wrap_text(line, mono, SAFE - 48):
            draw.text((X0 + 24, y + 24), wrapped, font=mono, fill=alpha_color(GREEN, a))
            y += 28
        y += 12
    y += 40
    specs = [
        "Minimum: 2 vCPU · 2 GB RAM (SQLite dev)",
        "Recommended: 2 vCPU · 4 GB RAM (PostgreSQL)",
        "PostgreSQL 16 · pgvector/pgvector:pg16",
    ]
    for s in specs:
        draw.text((X0, y), s, font=mono, fill=alpha_color(MUTED, a))
        y += 32


def mock_embedding(draw: ImageDraw.ImageDraw, a: float) -> None:
    mono = _font(FONT_MONO, 20)
    sans_b = _font(FONT_SANS_BOLD, 28)
    text_center(draw, 160, "SEMANTIC SEARCH", sans_b, TEXT, a)
    text_center(draw, 210, "CPU-only · no GPU required", mono, MUTED, a)
    card(draw, X0, 300, SAFE, 200, a, True)
    draw.text((X0 + 24, 330), "Model", font=mono, fill=alpha_color(MUTED, a))
    draw.text((X0 + 24, 360), "BAAI/bge-small-en-v1.5", font=_font(FONT_MONO, 24), fill=alpha_color(TEXT, a))
    draw.text((X0 + 24, 410), "Runtime · fastembed on CPU", font=mono, fill=alpha_color(MUTED, a))
    draw.text((X0 + 24, 450), "Find related CVEs by meaning", font=mono, fill=alpha_color(TEXT, a))


def cta_banner(draw: ImageDraw.ImageDraw, lines: list[str], a: float) -> None:
    y = H - 280
    card(draw, X0, y, SAFE, 40 + len(lines) * 36, a, True)
    mono = _font(FONT_MONO, 22)
    ty = y + 20
    for line in lines:
        draw.text((X0 + 24, ty), line, font=mono, fill=alpha_color(TEXT, a))
        ty += 36


@dataclass
class Scene:
    sec: float
    fn: Callable[[Image.Image, ImageDraw.ImageDraw, int, int], None]


def render_all(scenes: list[Scene], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="briefr-reel-") as tmp:
        tmp_path = Path(tmp)
        idx = 0
        for scene in scenes:
            n = int(scene.sec * FPS)
            for i in range(n):
                img = new_frame()
                d = ImageDraw.Draw(img)
                scene.fn(img, d, i, n)
                img.save(tmp_path / f"f_{idx:06d}.png")
                idx += 1
        subprocess.run(
            [
                "ffmpeg", "-y", "-framerate", str(FPS),
                "-i", str(tmp_path / "f_%06d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
    print(f"Wrote {out} ({idx / FPS:.1f}s)")


def scene_logo_intro(sec: float) -> Scene:
    def fn(img, d, i, n):
        p = ease_out(i / max(1, n - 1))
        draw_brand_lockup(d, img, H // 2 - 60, p)
        if p > 0.5:
            text_center(d, H // 2 + 100, "CVE intelligence you self-host", _font(FONT_SANS, 28), MUTED, ease_out((p - 0.5) * 2))
    return Scene(sec, fn)


def scene_with_shot_or_mock(sec: float, shot: str, mock_fn, scroll: float = 0.0) -> Scene:
    base = load_shot(shot)

    def fn(img, d, i, n):
        p = ease_out(i / max(1, n * 0.35))
        dy = int((1 - p) * 20)
        if base:
            overlay = base.copy()
            dark = Image.new("RGB", (W, H), BG)
            img.paste(Image.blend(dark, overlay, 0.92))
        mock_fn(d, p, dy, scroll) if mock_fn.__code__.co_argcount >= 4 else mock_fn(d, p, dy)
    return Scene(sec, fn)


def blit_shot(img: Image.Image, shot: str, y: int = 0, alpha: float = 0.88) -> bool:
    base = load_shot(shot)
    if not base:
        return False
    dark = Image.new("RGB", (W, H), BG)
    layer = Image.blend(dark, base, alpha)
    img.paste(layer, (0, y))
    return True


def build_cut1() -> list[Scene]:
    """45s product hook — what it solves, stack priority, CVE detail, IOC, PDF, self-host."""
    return [
        Scene(3.0, lambda img, d, i, n: draw_brand_lockup(d, img, H // 2 - 40, i / max(1, n - 1))),
        Scene(5.0, lambda img, d, i, n: (
            text_center(d, 120, "What changed in 24 hours?", _font(FONT_SERIF, 40), TEXT, ease_out(i / (n * 0.35))),
            blit_shot(img, "morning-brief.png", 180) or mock_morning_brief(d, ease_out(i / (n * 0.5)), int((1 - ease_out(i / (n * 0.4))) * 16)),
        )),
        Scene(6.0, lambda img, d, i, n: (
            text_center(d, 100, "Stack-prioritized CVEs", _font(FONT_SANS_BOLD, 26), ACCENT, ease_out(i / (n * 0.3))),
            blit_shot(img, "cve-feed.png", 140) or mock_feed_stack(d, ease_out(i / (n * 0.4))),
        )),
        Scene(7.0, lambda img, d, i, n: mock_cve_detail(d, ease_out(i / (n * 0.35)), int((1 - ease_out(i / (n * 0.35))) * 14), i / max(1, n - 1) * 0.3)),
        Scene(7.0, lambda img, d, i, n: (
            text_center(d, 90, "IP · hash · domain lookup", _font(FONT_MONO, 24), MUTED, ease_out(i / (n * 0.3))),
            blit_shot(img, "ioc-lookup.png", 120) or mock_ioc_graph(d, i / max(1, n - 1)),
        )),
        Scene(8.0, lambda img, d, i, n: mock_pdf_page(d, ease_out(i / (n * 0.35)), i / max(1, n - 1))),
        Scene(5.0, lambda img, d, i, n: (
            cta_banner(d, [
                "Free & open source · Apache 2.0",
                "Optional free-tier API keys (VirusTotal, AbuseIPDB, GreyNoise)",
                "Self-hosted · your data stays yours",
                "Min 2 vCPU · 2 GB RAM  |  Rec. 4 GB with PostgreSQL",
            ], ease_out(i / (n * 0.4))),
            draw_brand_lockup(d, img, H - 120, ease_out(i / (n * 0.5))),
        )),
    ]


def build_cut2() -> list[Scene]:
    """90s scoring, correlation, embeddings — deep dive on intelligence layer."""
    return [
        Scene(4.0, lambda img, d, i, n: (
            draw_brand_lockup(d, img, 120, ease_out(i / (n * 0.5)), 0),
            text_center(d, 260, "How BRIEFR scores & connects CVEs", _font(FONT_SERIF, 40), TEXT, ease_out(i / (n * 0.4))),
        )),
        Scene(18.0, lambda img, d, i, n: mock_risk_bars(d, i / max(1, n - 1))),
        Scene(14.0, lambda img, d, i, n: (
            text_center(d, 150, "Stack-aware asset matching", _font(FONT_SANS_BOLD, 28), TEXT, 1.0),
            mock_feed_stack(d, ease_out(i / (n * 0.35))),
        )),
        Scene(18.0, lambda img, d, i, n: mock_correlation(d, i / max(1, n - 1))),
        Scene(16.0, lambda img, d, i, n: mock_embedding(d, ease_out(i / (n * 0.4)))),
        Scene(12.0, lambda img, d, i, n: (
            text_center(d, 200, "Scheduler precomputes · API reads cached results", _font(FONT_MONO, 22), MUTED, ease_out(i / (n * 0.4))),
            text_center(d, 260, "Same CVE + same stack = same score, every time", _font(FONT_SANS, 26), TEXT, ease_out(i / (n * 0.5))),
            draw_brand_lockup(d, img, H - 200, ease_out(i / (n * 0.5))),
        )),
        Scene(8.0, lambda img, d, i, n: draw_brand_lockup(d, img, H // 2 - 40, ease_out(i / (n * 0.5)))),
    ]


def build_cut3() -> list[Scene]:
    """90s data pipeline & deployment."""
    return [
        Scene(4.0, lambda img, d, i, n: (
            draw_brand_lockup(d, img, 120, ease_out(i / (n * 0.5))),
            text_center(d, 260, "Where your data lives", _font(FONT_SERIF, 40), TEXT, ease_out(i / (n * 0.4))),
        )),
        Scene(22.0, lambda img, d, i, n: mock_data_hub(d, i / max(1, n - 1))),
        Scene(14.0, lambda img, d, i, n: (
            text_center(d, 150, "Intel schema · app schema · one database", _font(FONT_MONO, 22), MUTED, 1.0),
            card(d, X0, 220, SAFE, 160, 1.0, True),
            d.text((X0 + 24, 250), "Scheduler writes feeds & jobs", font=_font(FONT_MONO, 22), fill=TEXT),
            d.text((X0 + 24, 290), "FastAPI reads precomputed rows", font=_font(FONT_MONO, 22), fill=TEXT),
            d.text((X0 + 24, 330), "No separate queue to deploy", font=_font(FONT_MONO, 22), fill=MUTED),
        )),
        Scene(24.0, lambda img, d, i, n: mock_deploy(d, ease_out(i / (n * 0.35)))),
        Scene(14.0, lambda img, d, i, n: (
            cta_banner(d, [
                "One deployment · one PostgreSQL 16 instance",
                "pgvector enabled for embeddings & SigmaHQ index",
                "All public feeds · generous free API tiers",
            ], ease_out(i / (n * 0.4))),
            draw_brand_lockup(d, img, H - 140, ease_out(i / (n * 0.5))),
        )),
        Scene(8.0, lambda img, d, i, n: draw_brand_lockup(d, img, H // 2 - 40, ease_out(i / (n * 0.5)))),
    ]


def build_cut4() -> list[Scene]:
    """60s LinkedIn — fast product montage + CTA."""
    return [
        Scene(2.0, lambda img, d, i, n: draw_brand_lockup(d, img, H // 2 - 40, i / max(1, n - 1))),
        Scene(5.0, lambda img, d, i, n: mock_morning_brief(d, ease_out(i / (n * 0.4)))),
        Scene(5.0, lambda img, d, i, n: mock_feed_stack(d, ease_out(i / (n * 0.4)))),
        Scene(6.0, lambda img, d, i, n: mock_cve_detail(d, ease_out(i / (n * 0.35)), 0, 0)),
        Scene(6.0, lambda img, d, i, n: mock_ioc_graph(d, i / max(1, n - 1))),
        Scene(8.0, lambda img, d, i, n: mock_risk_bars(d, min(1.0, i / (n * 0.8)))),
        Scene(10.0, lambda img, d, i, n: mock_pdf_page(d, ease_out(i / (n * 0.35)), i / max(1, n - 1) * 0.2)),
        Scene(8.0, lambda img, d, i, n: (
            text_center(d, 220, "Completely free to run", _font(FONT_SERIF, 48), ACCENT, ease_out(i / (n * 0.35))),
            text_center(d, 300, "Open source · self-hosted · optional free API keys", _font(FONT_MONO, 22), MUTED, ease_out(i / (n * 0.45))),
            cta_banner(d, ["github.com/Soldier0x0/briefr"], ease_out(i / (n * 0.5))),
        )),
        Scene(8.0, lambda img, d, i, n: draw_brand_lockup(d, img, H // 2 - 20, ease_out(i / (n * 0.5)))),
    ]


CUTS = {
    "briefr-cut1-product-hook-45s.mp4": build_cut1,
    "briefr-cut2-scoring-correlation-90s.mp4": build_cut2,
    "briefr-cut3-data-deploy-90s.mp4": build_cut3,
    "briefr-cut4-linkedin-60s.mp4": build_cut4,
}


def export_logo_png() -> None:
    """Rasterize SVG wordmarks via ffmpeg/librsvg if available."""
    for svg_name in ("logo-wordmark-stacked.svg", "logo-wordmark-horizontal.svg"):
        svg = BRAND_DIR / svg_name
        png = svg.with_suffix(".png")
        if png.exists():
            continue
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-w", "800", "-o", str(png), str(svg)], check=False)


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg required")
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    export_logo_png()
    for name, builder in CUTS.items():
        render_all(builder(), OUT_DIR / name)
    print(f"\nDone → {OUT_DIR}")
    print("Add F5 TTS audio from docs/marketing/reel-f5-tts-speak-only.txt")


if __name__ == "__main__":
    main()
