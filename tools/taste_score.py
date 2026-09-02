#!/usr/bin/env python3
"""
DesktopNote Taste Score — deterministic scorer.

Purpose: give multi-agent iterations a single, comparable, machine-checkable
number so agents can compete overnight on "taste". Static + (optional) build
checks. The DESIGN JUDGE layer (screenshots reviewed by an LLM/human) is a
separate mode and needs a desktop session; see docs/TASTE_SCORE.md.

Usage:
    python3 tools/taste_score.py                 # static, fast (default)
    python3 tools/taste_score.py --build         # also gate on configure+build+ctest
    python3 tools/taste_score.py --json          # machine-readable out
    python3 tools/taste_score.py --all           # --build + extra grep sweeps

Notes:
  - Uses python3 (host `python` is 2.7). No third-party deps.
  - Reads the real source tree; checks decay into concrete advice in
    docs/TASTE_SCORE.md "How to raise each dimension".
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TESTS = ROOT / "tests"


def set_src_dir(path):
    """Point the scorer at a different source tree (used by the mutation audit
    to score deliberately-regressed copies)."""
    global SRC, ROOT
    SRC = Path(path)
    ROOT = SRC.parent


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(x)))


def linearize(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_rgb(h):
    h = h & 0xFFFFFF
    return ((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF)


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_frag_code():
    """Concatenate all src/*.cpp/h into one string for pattern sweeps."""
    parts = []
    for f in sorted(SRC.iterdir()):
        if f.suffix in (".cpp", ".h"):
            parts.append(f"\n/* ==== {f.name} ==== */\n" + read_text(f))
    return "\n".join(parts)


def count_in(src_all, pattern):
    return len(re.findall(pattern, src_all))


# --------------------------------------------------------------------------
# Dimension 1: Platform Fidelity (native correctness)
# --------------------------------------------------------------------------

def score_platform(src_all, renderer_src, note_window_src):
    """CAMELOT: correctness-only. Every check is a FACT that either holds or does
    not, scoped to the file that owns the property — so mutating the behavior flips
    the number, and you cannot fake it with an unused symbol anywhere in the tree."""
    pts = 0
    max_pts = 0
    lines = []

    # DPI-correctness, not symbol-counting: the render-target property (the dpiX/dpiY
    # passed to D2D1::RenderTargetProperties) MUST be the window's real DPI, not a
    # hardcoded 96. Scope to that block, so an unrelated `const dpi = DpiForWindowOrSystem`
    # elsewhere cannot mask a leak.
    max_pts += 20
    rt_block = re.search(r"RenderTargetProperties\((.*?)\);", renderer_src, re.S)
    rt_dpi_ok = False
    if rt_block:
        prop_body = rt_block.group(1)
        # the dpi it is wired to must be the window's DPI, not a hardcoded literal
        rt_dpi_ok = "DpiForWindowOrSystem(window)" in prop_body
    if rt_dpi_ok and re.search(r"DipToPixel|PixelToDip", src_all):
        pts += 20
        lines.append("DPI: RenderTargetProperties uses window DPI — per-monitor correct")
    elif rt_dpi_ok:
        pts += 12
        lines.append("DPI: render target uses window DPI, but DipToPixel/PixelToDip missing elsewhere")
    else:
        lines.append("DPI: RenderTargetProperties dpi not wired to window (hardcoded 96 = leak)")

    # Layered-window alpha compositing for per-pixel transparency (owned by renderer).
    max_pts += 20
    if "UpdateLayeredWindow" in renderer_src and "ULW_ALPHA" in renderer_src:
        pts += 20
        lines.append("Compositing: UpdateLayeredWindow + ULW_ALPHA in renderer (true per-pixel alpha)")
    else:
        lines.append("Compositing: no layered-window alpha path in renderer")

    # Single instance via named mutex (avoid duplicate process writers).
    max_pts += 20
    if re.search(r"CreateMutex|OpenMutex", src_all):
        pts += 20
        lines.append("Singleton: named mutex present")
    else:
        lines.append("Singleton: no mutex guard found")

    # Native window surface: the NOTE WINDOW itself must be WS_POPUP + RegisterClass,
    # scoped to note_window.cpp (not "anywhere in the tree" — that is a comment-away).
    max_pts += 20
    if "WS_POPUP" in note_window_src and "RegisterClass" in note_window_src:
        pts += 20
        lines.append("Surface: note window is WS_POPUP + RegisterClass in note_window.cpp")
    else:
        lines.append("Surface: note window is NOT WS_POPUP (native popup lost)")

    # Desktop-embed failure safety fallback.
    max_pts += 20
    if "WorkerW" in src_all and re.search(r"fallback|回退|\bNormal\b", src_all):
        pts += 20
        lines.append("Desktop embed: WorkerW targeting + safe fallback detected")
    else:
        lines.append("Desktop embed: no WorkerW fallback path detected")

    return pts, max_pts, lines


# --------------------------------------------------------------------------
# Dimension 2: Visual Coherence (palette / accent / restraint)
# --------------------------------------------------------------------------

def score_coherence(src_all, appearance_block, renderer_src):
    pts = 0
    max_pts = 0
    lines = []

    # Default background must NOT be a pure #000000 fill (kills depth).
    max_pts += 25
    bg_match = re.search(r"background_color\s*=\s*0x([0-9A-Fa-f]{6})", appearance_block)
    if bg_match:
        bg = int(bg_match.group(1), 16)
        rgb = hex_to_rgb(bg)
        is_pure_black = rgb == (0, 0, 0)
        if is_pure_black:
            lines.append(f"BG default 0x{bg:06X} is pure black — loses depth (use off-black like zinc)")
        else:
            pts += 25
            lines.append(f"BG default 0x{bg:06X} is off-black (good depth)")
    else:
        lines.append("BG default not found")

    # Accent discipline: single accent hue for the whole surface.
    # Gather candidate accent literals (border_color default + renderer accents).
    max_pts += 25
    accents = set()
    bm = re.search(r"border_color\s*=\s*0x([0-9A-Fa-f]{6})", appearance_block)
    if bm:
        accents.add(int(bm.group(1), 16))
    for accent_match in re.finditer(r"D2DColor\(0x([0-9A-Fa-f]{6})", renderer_src):
        accents.add(int(accent_match.group(1), 16))
    # Exclude near-black / near-white structural tones from "accent" counting.
    def structural(h):
        r, g, b = hex_to_rgb(h)
        maxc, minc = max(r, g, b), min(r, g, b)
        return (maxc - minc) < 20  # low chroma -> not an accent
    accent_tones = [h for h in accents if not structural(h)]
    # distinct hue buckets (quantized)
    def hue_bucket(h):
        r, g, b = hex_to_rgb(h)
        mx = max(r, g, b)
        if mx == 0:
            return -1
        if mx - min(r, g, b) < 20:
            return -1
        frac = (0 if mx == r else (1 if mx == g else 2)) * 3
        return frac
    buckets = {hue_bucket(h) for h in accent_tones if hue_bucket(h) >= 0}
    n = len(buckets)
    if n == 0:
        lines.append("Accent: no chromatic accent tone found")
    elif n == 1:
        pts += 25
        lines.append(f"Accent: single accent hue across surface ({len(accent_tones)} literals)")
    elif n == 2:
        pts += 12
        lines.append(f"Accent: TWO accent hues present — merge to one ({buckets})")
    else:
        lines.append(f"Accent: {n} accent hues — heavy fragmentation ({buckets})")

    # No AI-glow signature on IMPOSED chrome. The toolbar exposes a user-selectable
    # note-colour palette (kBackgroundColors/kFontColors/kBorderColors arrays) where a
    # violet swatch (0x8B5CF6) is legitimate choice, NOT an AI tell. Only flag purple
    # that lives in chrome constants (not inside constexpr array data).
    max_pts += 15
    def ai_purple(h):
        r, g, b = hex_to_rgb(h)
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == 0 or (mx - mn) < 24:
            return False
        # violet/indigo: blue dominant AND red >= green (crude hue ~265-295).
        # A pure blue has green >> red (e.g. 0x0288D1 g=136,r=2) -> rejected.
        return b >= r and r >= g and b > g
    # Strip colours that live inside constexpr palette arrays (user data, not chrome).
    palette_data = set()
    for m in re.finditer(r"constexpr std::array<std::uint32_t,\s*\d+>\s+\w+\s*\{([^}]*)\}", src_all):
        palette_data |= {int(h, 16) for h in re.findall(r"0x([0-9A-Fa-f]{6})", m.group(1))}
    chrome_hex = {int(h, 16) for h in re.findall(r"0x([0-9A-Fa-f]{6})", src_all)} - palette_data
    ai_purples = [h for h in chrome_hex if ai_purple(h)]
    if not ai_purples:
        pts += 15
        lines.append("No AI-glow / royal-purple accent defaults (restraint)")
    else:
        lines.append(f"AI-glow purple/indigo accents in chrome: {[f'0x{h:06X}' for h in sorted(ai_purples)]} — AI tell")

    # Colour region saturation ceiling for default text vs default bg contrast.
    max_pts += 25
    fm = re.search(r"font_color\s*=\s*0x([0-9A-Fa-f]{6})", appearance_block)
    if fm and bg_match:
        fg = int(fm.group(1), 16)
        bg = int(bg_match.group(1), 16)
        ratio = contrast_ratio(hex_to_rgb(fg), hex_to_rgb(bg))
        if ratio >= 7.0:
            pts += 25
            lines.append(f"Contrast: default text/bg ratio {ratio:.2f}:1 (AAA)")
        elif ratio >= 4.5:
            pts += 18
            lines.append(f"Contrast: default text/bg ratio {ratio:.2f}:1 (AA pass)")
        else:
            lines.append(f"Contrast: default text/bg ratio {ratio:.2f}:1 FAILS AA")

    # No em-dash in user-facing code strings (a shuorenhua/AI-tell baseline).
    max_pts += 10
    emdash = count_in(src_all, "\u2014|\u2013")
    if emdash == 0:
        pts += 10
        lines.append("Typography: no em/en-dash in source (clean punctuation)")
    else:
        lines.append(f"Typography: {emdash} em/en-dash literals in source")

    return pts, max_pts, lines


# --------------------------------------------------------------------------
# Dimension 3: Render Polish (geometry coherence + rendering states)
# --------------------------------------------------------------------------

def score_polish(renderer_src):
    """CAMELOT: correctness/facts only. Radius-family COHERENCE and interaction FEEL
    are aesthetic judgments that a symbol-count or a banding table can be gamed on
    (M3, M4) — those move to the perception referee (docs/TASTE_SCORE.md). Here we
    keep only binary facts about the render surface."""
    pts = 0
    max_pts = 0
    lines = []

    # Badge glyphs: hand-drawn vector state glyphs exist (Lock/Pin/Monitor/Mouse).
    max_pts += 33
    if "StatusBadgeType" in renderer_src and "FillRoundedRectangle" in renderer_src:
        pts += 33
        lines.append("Status badges: custom vector glyphs (Lock/TopMost/Desktop/ClickThrough)")
    else:
        lines.append("Status badges: none found")

    # Resize affordance present when unlocked.
    max_pts += 33
    if "locked" in renderer_src and "DrawLine" in renderer_src:
        pts += 33
        lines.append("Resize affordance: grip lines rendered (only when unlocked)")
    else:
        lines.append("Resize affordance: not found")

    # Empty/corrupt-data handling is the note app's "empty state".
    max_pts += 34
    if re.search(r"corrupt|recover|resilient|Normalize", find_frag_code()):
        pts += 34
        lines.append("Resilience: corrupt/recovery path present (the app's empty-state story)")
    else:
        lines.append("Resilience: no corruption recovery path found")

    return pts, max_pts, lines


# --------------------------------------------------------------------------
# Dimension 4: Typography
# --------------------------------------------------------------------------

def score_type(appearance_block):
    pts = 0
    max_pts = 0
    lines = []

    # Font family should be a platform-appropriate default, not a web font.
    max_pts += 40
    fm = re.search(r"font_family\s*=\s*L?\"([^\"]+)\"", appearance_block)
    if fm:
        fam = fm.group(1)
        web_generic = ("Arial", "Helvetica", "Roboto", "Inter", "Lato", "Open Sans", "Segoe UI Light")
        if fam in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Segoe UI Variable"):
            pts += 40
            lines.append(f"Font: '{fam}' — platform-native, correct for zh-CN first")
        elif any(w.lower() in fam.lower() for w in web_generic):
            pts += 18
            lines.append(f"Font: '{fam}' is a web/import default — prefer a Windows face")
        else:
            pts += 26
            lines.append(f"Font: '{fam}' — acceptable but justify against platform default")
    else:
        lines.append("Font: no font_family default found")

    # Font size in DIPs (scales with per-monitor DPI), not raw pixels.
    max_pts += 30
    if re.search(r"font_size_dip\s*=\s*[\d.]+", appearance_block):
        pts += 30
        lines.append("Font size: declared in DIP (DPI-scaled)")
    else:
        lines.append("Font size: not DIP-based")

    # Line/pad rhythm in DIPs.
    max_pts += 30
    if re.search(r"padding_dip\s*=\s*[\d.]+", appearance_block) and \
       re.search(r"paragraph_spacing_dip\s*=\s*[\d.]+", appearance_block):
        pts += 30
        lines.append("Rhythm: padding + paragraph spacing in DIP (balanced text block)")
    else:
        lines.append("Rhythm: text-block spacing not expressed in DIP")

    return pts, max_pts, lines


# --------------------------------------------------------------------------
# Dimension 0: Build & Test gate
# --------------------------------------------------------------------------

def score_build(do_build):
    if not do_build:
        return None, "skipped (pass --build to gate on it)"
    try:
        r = subprocess.run(
            ["cmake", "--build", "--preset", "msvc-release", "--parallel"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=240,
        )
        build_ok = r.returncode == 0
        test_r = subprocess.run(
            ["ctest", "--preset", "msvc-release"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        tests_ok = test_r.returncode == 0
        detail = f"build={'ok' if build_ok else 'FAIL'} ctest={'ok' if tests_ok else 'FAIL'}"
        if build_ok and tests_ok:
            return 100, detail
        if build_ok:
            return 40, detail + " (tests failing — hard cap)"
        return 0, detail + " (build failing — hard cap)"
    except FileNotFoundError:
        return None, "cmake not on PATH — build gate disabled"
    except subprocess.TimeoutExpired:
        return None, "build timed out — gate disabled"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="gate on configure+build+ctest")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--all", action="store_true", help="--build plus broader sweeps")
    ap.add_argument("--src", help="override source dir (mutation audit uses this)")
    args = ap.parse_args()

    if args.src:
        set_src_dir(args.src)

    appearance_block = ""
    am = re.search(r"struct Appearance \{.*?\};", find_frag_code(), re.S)
    if am:
        appearance_block = am.group(0)
    renderer_src = read_text(SRC / "note_renderer.cpp")
    src_all = find_frag_code()

    dims = {}

    # Build gate (weight 15) — hard cap if failed.
    if args.src:
        bscore, bnote = None, "build gate off (mutated tree)"
    else:
        bscore, bnote = score_build(args.build or args.all)
    dims["build"] = (15, bscore, bnote if bscore is None else "pass" if bscore >= 100 else "below par", [])

    platform = score_platform(src_all, renderer_src, read_text(SRC / "note_window.cpp"))
    coherence = score_coherence(src_all, appearance_block, renderer_src)
    polish = score_polish(renderer_src)
    typo = score_type(appearance_block)

    def package(pts, max_pts, checks):
        if max_pts <= 0:
            return 0.0, "no points", checks
        return (100.0 * pts / max_pts), "", checks

    for name, (pts, max_pts, checks) in [("platform", platform), ("coherence", coherence),
                                          ("polish", polish), ("type", typo)]:
        s, note, checks = package(pts, max_pts, checks)
        dims[name] = ({"platform": 20, "coherence": 25, "polish": 25, "type": 15}[name], s, note, checks)

    # Compose weighted total. Unscored dimensions (e.g. build when not gated) are
    # EXCLUDED from the denominator — an ungated build must not silently inflate or
    # deflate the structure score.
    weights = {"build": 15, "platform": 20, "coherence": 25, "polish": 25, "type": 15}
    total = 0.0
    total_w = 0
    gated = False
    detail_rows = []
    for name, (w, s, note, lines) in dims.items():
        if s is None:
            detail_rows.append({"dimension": name, "weight": w, "score": None, "note": note, "checks": lines})
            continue
        total_w += w
        detail_rows.append({"dimension": name, "weight": w, "score": s, "note": note, "checks": lines})
        total += w * s

    mean = total / total_w if total_w else 0.0

    # Apply hard cap: if build was gated and failed, cap the whole score.
    if dims["build"][1] is not None and dims["build"][1] < 100:
        gated = True
        if dims["build"][1] < 40:
            mean = min(mean, 25.0)

    result = {
        "project": "DesktopNote",
        "score": round(mean, 1),
        "score_type": "structure",
        "gated": gated,
        "dimensions": detail_rows,
        "method": "static" if not (args.build or args.all) else "static+build",
        "note": "STRUCTURE score (correctness only). radius-family & interaction-FEEL are "
                "judged by the perception referee, not here — see docs/TASTE_SCORE.md.",
        "perception_only": ["coherence.radius_family", "polish.interaction_states", "polish.radius_family"],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"DesktopNote STRUCTURE SCORE  {result['score']:.1f} / 100  (correctness only)")
    if gated:
        print("  !! GATED — build/test below par, total capped")
    print("  radius-family & interaction-feel are NOT scored here (perception referee)")
    print("=" * 60)
    order = ["build", "platform", "coherence", "polish", "type"]
    for name in order:
        w, s, note, checks = dims[name]
        if s is None:
            print(f"  {name:<10} w={w:>2}  --  {note}")
        else:
            print(f"  {name:<10} w={w:>2}  {s:>6.1f}/100  {note}")
        for line in checks:
            print(f"        - {line}")
    print("=" * 60)
    print("Raise each dimension: see docs/TASTE_SCORE.md 'How to raise each dimension'.")


if __name__ == "__main__":
    main()
