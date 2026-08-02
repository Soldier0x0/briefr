#!/usr/bin/env python3
"""Generate BRIEFR portrait marketing reels (1080x1920, 30fps, silent).

Public-facing motion graphics — no internal filename tags or engineer jargon.
Output: docs/marketing/reels/briefr-cut{1-4}.mp4

Requires: Pillow, ffmpeg on PATH.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "marketing" / "reels"
FPS = 30
W, H = 1080, 1920
SAFE_W = 900

# BRIEFR tokens
BG = (10, 10, 8)
SURFACE = (18, 18, 17)
CARD = (18, 18, 17)
BORDER = (42, 42, 37)
TEXT = (232, 230, 223)
MUTED = (167, 163, 150)
FAINT = (108, 106, 98)
ACCENT = (232, 85, 51)
ACCENT_GLOW = (232, 85, 51, 36)

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def fade_up(alpha: float, dy: float = 14.0) -> tuple[float, int]:
    a = ease_out(alpha)
    return a, int((1.0 - a) * dy)


def new_frame() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def draw_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, ...] = TEXT,
    alpha: float = 1.0,
    dy: int = 0,
) -> None:
    if alpha <= 0:
        return
    color = fill if len(fill) == 3 else fill[:3]
    if alpha < 1.0:
        color = tuple(int(c * alpha) for c in color)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y + dy), text, font=font, fill=color)


def draw_left_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, ...] = TEXT,
    line_gap: int = 8,
    alpha: float = 1.0,
    dy: int = 0,
) -> int:
    cy = y + dy
    color = tuple(int(c * alpha) for c in fill[:3]) if alpha < 1.0 else fill
    for line in lines:
        draw.text((x, cy), line, font=font, fill=color)
        cy += font.size + line_gap
    return cy


def draw_card(
    img: Image.Image,
    x: int,
    y: int,
    w: int,
    h: int,
    alpha: float = 1.0,
    accent_left: bool = False,
) -> None:
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    fill = (*CARD, int(255 * alpha))
    border = (*BORDER, int(255 * alpha))
    od.rounded_rectangle((0, 0, w - 1, h - 1), radius=8, fill=fill, outline=border, width=1)
    if accent_left:
        od.rectangle((0, 0, 4, h), fill=(*ACCENT, int(255 * alpha)))
    img.paste(overlay, (x, y), overlay)


def terminal_line(draw: ImageDraw.ImageDraw, text: str, y: int, progress: float) -> None:
    mono = _font(FONT_MONO, 34)
    shown = text[: max(0, int(len(text) * progress))]
    draw.text((W // 2 - 420, y), shown, font=mono, fill=TEXT)
    if progress < 1.0 and int(progress * 20) % 2 == 0:
        bx = W // 2 - 420 + mono.getlength(shown)
        draw.rectangle((bx, y + 4, bx + 14, y + 34), fill=ACCENT)


def cursor_blink(draw: ImageDraw.ImageDraw, y: int, frame: int) -> None:
    if frame % 30 < 15:
        cx = W // 2
        draw.rectangle((cx - 7, y, cx + 7, y + 30), fill=ACCENT)


@dataclass
class Scene:
    duration_sec: float
    render: Callable[[Image.Image, ImageDraw.ImageDraw, int, int], None]


def render_scenes(scenes: list[Scene], out_path: Path) -> None:
    total_frames = sum(int(s.duration_sec * FPS) for s in scenes)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="briefr-reel-") as tmp:
        tmp_path = Path(tmp)
        frame_idx = 0
        for scene in scenes:
            n = int(scene.duration_sec * FPS)
            for i in range(n):
                img = new_frame()
                draw = ImageDraw.Draw(img)
                scene.render(img, draw, i, n)
                img.save(tmp_path / f"frame_{frame_idx:06d}.png")
                frame_idx += 1
        pattern = str(tmp_path / "frame_%06d.png")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                pattern,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "20",
                "-preset",
                "fast",
                str(out_path),
            ],
            check=True,
            capture_output=True,
        )
    print(f"Wrote {out_path} ({total_frames} frames, {total_frames / FPS:.1f}s)")


def scene_black_hold(sec: float) -> Scene:
    return Scene(sec, lambda img, draw, i, n: None)


def scene_cursor(sec: float) -> Scene:
    y = H // 2

    def render(img, draw, i, n):
        cursor_blink(draw, y, i)

    return Scene(sec, render)


def scene_terminal_type(sec: float, line: str) -> Scene:
    y = H // 2 - 20

    def render(img, draw, i, n):
        progress = ease_out(i / max(1, n - 1))
        terminal_line(draw, line, y, progress)

    return Scene(sec, render)


def scene_headline(sec: float, text: str, sub: str | None = None) -> Scene:
    def render(img, draw, i, n):
        a, dy = fade_up(i / max(1, n * 0.6))
        serif = _font(FONT_SERIF, 64)
        draw_centered(draw, H // 2 - 80, text, serif, TEXT, a, dy)
        if sub:
            sans = _font(FONT_SANS, 30)
            draw_centered(draw, H // 2 + 20, sub, sans, MUTED, a, dy)

    return Scene(sec, render)


def scene_feed_montage(sec: float, labels: list[str]) -> Scene:
    chunk = sec / len(labels)
    x0 = (W - SAFE_W) // 2

    def render(img, draw, i, n):
        idx = min(len(labels) - 1, int(i / FPS / chunk))
        shown = labels[: idx + 1]
        card_h = 72
        gap = 16
        total_h = len(shown) * (card_h + gap) - gap
        y0 = H // 2 - total_h // 2
        for j, label in enumerate(shown):
            local_i = i - int(j * chunk * FPS)
            if local_i < 0:
                continue
            local_n = int(chunk * FPS)
            a, dy = fade_up(local_i / max(1, local_n * 0.5))
            cy = y0 + j * (card_h + gap)
            draw_card(img, x0, cy + dy, SAFE_W, card_h, a, accent_left=True)
            mono = _font(FONT_MONO, 28)
            draw.text((x0 + 24, cy + 20 + dy), label, font=mono, fill=TEXT if a >= 1 else tuple(int(c * a) for c in TEXT))

    return Scene(sec, render)


def scene_source_groups(sec: float, groups: list[tuple[str, str]]) -> Scene:
    x0 = (W - SAFE_W) // 2

    def render(img, draw, i, n):
        step = sec / len(groups)
        visible = min(len(groups), int(i / FPS / step) + 1)
        y = H // 2 - 280
        for g in range(visible):
            title, body = groups[g]
            gi = i - int(g * step * FPS)
            gn = int(step * FPS)
            a, dy = fade_up(gi / max(1, gn * 0.5))
            draw_card(img, x0, y + dy, SAFE_W, 120, a, accent_left=True)
            draw.text((x0 + 20, y + 14 + dy), title, font=_font(FONT_SANS_BOLD, 22), fill=ACCENT if a >= 1 else tuple(int(c * a) for c in ACCENT))
            draw.text((x0 + 20, y + 48 + dy), body, font=_font(FONT_MONO, 20), fill=MUTED if a >= 1 else tuple(int(c * a) for c in MUTED))
            y += 130 + dy

    return Scene(sec, render)


def scene_risk_score(sec: float, score: int = 87) -> Scene:
    factors = [
        ("Asset match", 0.35),
        ("KEV listed", 0.25),
        ("EPSS", 0.15),
        ("Exploit available", 0.10),
        ("CVSS", 0.10),
        ("Momentum", 0.05),
    ]
    x0 = (W - SAFE_W) // 2

    def render(img, draw, i, n):
        a, dy = fade_up(min(1.0, i / (n * 0.3)))
        draw_card(img, x0, 280 + dy, SAFE_W, 520, a, accent_left=True)
        serif = _font(FONT_SERIF, 48)
        count_progress = ease_out(min(1.0, max(0.0, (i - n * 0.4) / (n * 0.25))))
        current = int(score * count_progress)
        draw.text((x0 + 32, 310 + dy), "Risk Score", font=_font(FONT_SANS, 24), fill=MUTED)
        draw.text((x0 + 32, 350 + dy), str(current), font=serif, fill=ACCENT)
        bar_x = x0 + 32
        bar_w = SAFE_W - 64
        y = 440 + dy
        for fi, (name, weight) in enumerate(factors):
            fi_start = n * 0.35 + fi * (n * 0.08)
            if i < fi_start:
                continue
            fa = ease_out(min(1.0, (i - fi_start) / (n * 0.06)))
            draw.text((bar_x, y), f"{name} — {weight:.2f}", font=_font(FONT_MONO, 20), fill=TEXT if fa >= 1 else tuple(int(c * fa) for c in TEXT))
            bw = int(bar_w * weight * fa)
            draw.rounded_rectangle((bar_x, y + 28, bar_x + bw, y + 40), radius=3, fill=ACCENT)
            y += 58

    return Scene(sec, render)


def scene_chips(sec: float, chips: list[str], title: str = "") -> Scene:
    x0 = (W - SAFE_W) // 2

    def render(img, draw, i, n):
        if title:
            a0, dy0 = fade_up(i / max(1, n * 0.2))
            draw_centered(draw, 300 + dy0, title, _font(FONT_SANS_BOLD, 28), TEXT, a0, 0)
        per = sec / (len(chips) + 1)
        y = 400
        for ci, chip in enumerate(chips):
            start = int(ci * per * FPS)
            if i < start:
                continue
            ca, cdy = fade_up((i - start) / max(1, FPS * 0.4))
            tw = _font(FONT_MONO, 24).getlength(chip) + 40
            cx = x0 + (SAFE_W - tw) // 2
            draw_card(img, int(cx), y + cdy, int(tw), 52, ca)
            draw.text((cx + 20, y + 14 + cdy), chip, font=_font(FONT_MONO, 24), fill=TEXT)
            y += 68

    return Scene(sec, render)


def scene_cost_card(sec: float, lines: list[str]) -> Scene:
    x0 = (W - SAFE_W) // 2

    def render(img, draw, i, n):
        draw_card(img, x0, 360, SAFE_W, 60 + len(lines) * 52, 1.0, accent_left=True)
        y = 390
        for li, line in enumerate(lines):
            start = int(li * (n / len(lines)) * 0.7)
            if i < start:
                continue
            la, ldy = fade_up((i - start) / max(1, FPS * 0.5))
            draw.text((x0 + 28, y + ldy), line, font=_font(FONT_MONO, 26), fill=TEXT if la >= 1 else tuple(int(c * la) for c in TEXT))
            y += 52

    return Scene(sec, render)


def scene_wordmark(sec: float, sub: str = "") -> Scene:
    def render(img, draw, i, n):
        a, dy = fade_up(i / max(1, n * 0.5))
        mono = _font(FONT_MONO, 72)
        draw_centered(draw, H // 2 - 60 + dy, "BRIEFR", mono, ACCENT, a)
        if sub:
            draw_centered(draw, H // 2 + 40 + dy, sub, _font(FONT_MONO, 26), MUTED, a)

    return Scene(sec, render)


SOURCE_GROUPS = [
    ("CVE & scoring", "NVD · CISA KEV · EPSS · OSV · Vulnrichment · MITRE ATT&CK"),
    ("Threat & exploit", "OTX · ExploitDB · Metasploit · Nuclei · ThreatFox"),
    ("IOC lookup (keys)", "VirusTotal · AbuseIPDB · GreyNoise · MalwareBazaar"),
    ("Detection & news", "SigmaHQ · RSS security feeds"),
]

COST_LINES = [
    "Software — free (Apache 2.0)",
    "CVE feeds — public",
    "IOC & AI — optional keys",
    "Hosting — you provide",
]


def build_cut1() -> list[Scene]:
    return [
        scene_black_hold(3.0),
        scene_cursor(0.5),
        scene_terminal_type(4.0, "$ every CVE you should care about"),
        scene_feed_montage(
            6.0,
            ["NVD", "CISA KEV", "FIRST EPSS", "AlienVault OTX", "ExploitDB · MITRE ATT&CK"],
        ),
        scene_risk_score(7.0),
        scene_headline(7.0, "Self-hosted.", "Open source. Yours."),
        scene_wordmark(7.5, "github.com/Soldier0x0/briefr"),
    ]


def build_cut2() -> list[Scene]:
    return [
        scene_black_hold(2.0),
        scene_terminal_type(8.0, "$ briefr — scores, correlates, briefs"),
        scene_source_groups(14.0, SOURCE_GROUPS[:2]),
        scene_risk_score(14.0),
        scene_headline(8.0, "Correlation", "Related CVEs through shared intel"),
        scene_chips(
            14.0,
            ["Sigma", "Elastic KQL", "Splunk SPL", "Sentinel KQL", "QRadar AQL"],
            "Detection starters",
        ),
        scene_headline(10.0, "Deterministic by default", "Optional AI for summaries"),
        scene_cost_card(12.0, COST_LINES),
        scene_wordmark(8.0, "github.com/Soldier0x0/briefr"),
    ]


def build_cut3() -> list[Scene]:
    return [
        scene_black_hold(2.0),
        scene_terminal_type(6.0, "$ CVE intelligence for security teams"),
        scene_source_groups(16.0, SOURCE_GROUPS),
        scene_risk_score(16.0),
        scene_headline(8.0, "Morning brief", "KEV · EPSS · stack · campaigns"),
        scene_chips(
            14.0,
            ["Sigma community", "SIEM queries", "Experimental labels"],
            "Detection",
        ),
        scene_headline(10.0, "Your data. Your server.", "Apache 2.0 · no per-seat license"),
        scene_cost_card(12.0, COST_LINES + ["Small VPS · no GPU required"]),
        scene_wordmark(6.0, "github.com/Soldier0x0/briefr"),
    ]


def build_cut4() -> list[Scene]:
    return [
        scene_black_hold(3.0),
        scene_terminal_type(5.0, "$ briefr — CVE intel you self-host"),
        scene_source_groups(12.0, SOURCE_GROUPS),
        scene_risk_score(12.0),
        scene_chips(
            12.0,
            ["Sigma", "Elastic", "Splunk", "Sentinel", "QRadar", "Morning brief"],
            "Workflow",
        ),
        scene_cost_card(8.0, COST_LINES),
        scene_wordmark(8.0, "github.com/Soldier0x0/briefr"),
    ]


CUTS = {
    "briefr-cut1-hook-35s.mp4": build_cut1,
    "briefr-cut2-walkthrough-90s.mp4": build_cut2,
    "briefr-cut3-teams-90s.mp4": build_cut3,
    "briefr-cut4-linkedin-60s.mp4": build_cut4,
}


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found on PATH")
    for name, builder in CUTS.items():
        render_scenes(builder(), OUT_DIR / name)
    print(f"\nAll reels written to {OUT_DIR}")
    print("Silent MP4s — lay F5 TTS audio from docs/marketing/reel-f5-tts-speak-only.txt")


if __name__ == "__main__":
    main()
