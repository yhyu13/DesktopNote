#!/usr/bin/env python3
"""
DesktopNote Taste Referee — the PERCEPTION layer (the real taste score).

The structure score (taste_score.py) asks "did it break". This referee asks
"is it good". It scores a RENDERED screenshot against a rubric. Two sub-layers:

  OBJECTIVE  — computable from pixels (contrast, accent consistency, no pure-black
               depth loss, text crispness proxy, edge/lines health). Hard to game:
               you cannot fake a JPEG with good contrast.
  AESTHETIC  — 1-5 rubric items that need a human/LLM to LOOK. These carry the
               aesthetic weight and the HIDDEN-SUBSET items an agent cannot
               rehearse against.

Goodhart note: the objective sub-layer is the anti-gaming anchor (pixel facts).
The aesthetic sub-layer is the taste authority — but only a judge LITERALLY LOOKING
should assign those scores; if you feed this script canned scores it is 0 value.

Usage:
  python3 tools/taste_referee.py --png <file>            # score one screenshot
  python3 tools/taste_referee.py --png <file> --json
  python3 tools/taste_referee.py --capture <pid> [--png out]   # live capture + score
  python3 tools/taste_referee.py --rubric-only          # print the rubric template (for a judge)

Need a desktop session to capture (headless CI has no interactive desktop).
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except Exception:  # noqa: BLE001
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(os.environ.get("TEMP", "/tmp"))


# --------------------------------------------------------------------------
# Rubric definitions.
# AESTHETIC items are public (agent-visible so it knows what's judged) but the
# SCORING judge should also apply HIDDEN items (held out) that it does NOT publish.
# --------------------------------------------------------------------------

PUBLIC_RUBRIC = [
    ("platform_polish", "Like a system first-party control, not a WebView/canvas paste-up"),
    ("color_harmony", "One accent color used consistently; neutrals coherent, no clashing"),
    ("state_feedback", "hover/press/focus/empty states evident (no static success-only)"),
    ("geometry_rhythm", "radii/padding follow one repeatable scale, not arbitrary micro-values"),
    ("text_quality", "crisp, correct DIP scaling, comfortable leading"),
]

HIDDEN_RUBRIC = [
    ("contrast_truthful", "text actually readable against its background (hard-confirm on pixels)"),
    ("no_ai_glow", "no purple/blue-violet gradient default on chrome"),
    ("chrome_consistency", "toolbar + note chrome share one accent; no orphan accent"),
    ("respects_transparency", "alpha transparency does not wash out text to unreadable"),
]

RUBRIC_WEIGHTS = {
    "platform_polish": 0.20, "color_harmony": 0.20, "state_feedback": 0.15,
    "geometry_rhythm": 0.15, "text_quality": 0.15, "contrast_truthful": 0.05,
    "no_ai_glow": 0.05, "chrome_consistency": 0.05, "respects_transparency": 0.05,
}


# --------------------------------------------------------------------------
# Objective pixel metrics (computed, not judged).
# --------------------------------------------------------------------------

def hex_to_rgb(h):
    h = h & 0xFFFFFF
    return ((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF)


def linearize(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def objective_metrics(im):
    """Compute objective, hard-to-game metrics from an RGBA image."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()

    # dominant background = most common opaque color among the OUTER region,
    # so dark TEXT glyphs do not pollute the background estimate.
    from collections import Counter
    cnt = Counter()
    # sample the perimeter band (rows 0-3 and h-4..h) and columns 0-3, w-4..w — this is
    # the chrome/surface, not the text block.
    coords = []
    for y in range(0, h):
        for x in (0, 1, 2, w - 3, w - 2, w - 1):
            coords.append((x, y))
    for y in (0, 1, 2, h - 3, h - 2, h - 1):
        for x in range(0, w):
            coords.append((x, y))
    for (x, y) in coords:
        r, g, b, a = px[x, y]
        if a > 250:
            cnt[(r, g, b)] += 1
    bg = cnt.most_common(1)[0][0] if cnt else (30, 30, 36)
    bg_is_pure_black = bg == (0, 0, 0)

    # dark glyph pixels in content area (text density). Must detect pixels that
    # CONTRAST with the dominant background — the off-black surface is itself dark,
    # so a "r,g,b < 120" test cannot distinguish text from background. Compare to bg.
    def far_from_bg(px_val):
        return (abs(px_val[0]-bg[0]) + abs(px_val[1]-bg[1]) + abs(px_val[2]-bg[2])) > 90
    dark_rows = 0
    for y in range(0, h):
        contrast = sum(1 for x in range(0, w)
                       if px[x, y][3] > 200 and far_from_bg(px[x, y]))
        if contrast > 8:
            dark_rows += 1

    # accent bar: top rows dominated by one strong chroma hue
    accent_rows = 0
    for y in range(0, min(6, h)):
        strong = sum(1 for x in range(w)
                     if max(px[x, y][:3]) - min(px[x, y][:3]) > 60 and px[x, y][3] > 200)
        if strong > w * 0.4:
            accent_rows += 1

    # AI-glow: does the strongest chroma in the TOP-LEFT region read as violet/indigo
    # (b>=r>=g)? A purple AI-tell. Sample chrome region only.
    violet_accents = 0
    for y in range(0, min(20, h)):
        for x in range(0, min(80, w)):
            r, g, b, a = px[x, y]
            if a > 200 and (b >= r and r >= g and b > g and (b - g) > 30):
                violet_accents += 1

    return {
        "background": bg,
        "bg_is_pure_black": bg_is_pure_black,
        "violet_accents": violet_accents,
        "text_rows": dark_rows,
        "accent_bar_rows": accent_rows,
        "width": w, "height": h,
    }


def objective_scores(m):
    """Convert objective metrics to 0-100 sub-scores. These are the anti-gaming facts."""
    out = {}
    bg = m.get("background", (30, 30, 36))
    # Contrast: text vs background — use the best available (white or black on bg).
    white_contrast = contrast_ratio((255, 255, 255), bg)
    black_contrast = contrast_ratio((0, 0, 0), bg)
    best = max(white_contrast, black_contrast)
    if best >= 7.0:
        out["contrast_truthful"] = 100.0
    elif best >= 4.5:
        out["contrast_truthful"] = 70.0
    elif best >= 3.0:
        out["contrast_truthful"] = 40.0
    else:
        out["contrast_truthful"] = 0.0

    # Depth: the BACKGROUND surface is pure black -> a tell. Off-black is fine.
    out["no_ai_glow"] = 100.0 if not m.get("bg_is_pure_black") else 30.0

    # Text present -> text quality proxy.
    out["text_quality"] = 100.0 if m["text_rows"] > 10 else (40.0 if m["text_rows"] > 0 else 0.0)

    # Accent exists (strong chroma top bar).
    out["chrome_consistency"] = 100.0 if m["accent_bar_rows"] >= 2 else 40.0

    # Penalise true violet/indigo AI-glow in chrome, reward restraint.
    out["platform_polish"] = 20.0 if m.get("violet_accents", 0) > 5 else 100.0

    return out


# --------------------------------------------------------------------------
# Capture (needs a desktop session).
# --------------------------------------------------------------------------

CAPTURE_PS = r"""
param([int]$TargetPid, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class R { public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder sb, int max);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; } }
"@
$noteHwnd = [IntPtr]::Zero
$cb = [R+EnumProc]{ param($hWnd,$lParam)
  $p=[uint32]0; [R]::GetWindowThreadProcessId($hWnd,[ref]$p)|Out-Null
  if($p -eq $TargetPid){ $sb=New-Object System.Text.StringBuilder 256; [R]::GetClassName($hWnd,$sb,256)|Out-Null
    if($sb.ToString() -eq 'DesktopNote.NoteWindow.v2'){ $script:noteHwnd=$hWnd } }
  return $true }
[R]::EnumWindows($cb,[IntPtr]::Zero)|Out-Null
if($noteHwnd -eq [IntPtr]::Zero){ Write-Output "WINDOW_NOT_FOUND"; exit 1 }
$rect=New-Object R+RECT; [R]::GetWindowRect($noteHwnd,[ref]$rect)|Out-Null
$w=$rect.R-$rect.L; $h=$rect.B-$rect.T
if($w -le 0){ Write-Output "BAD_RECT"; exit 1 }
$bmp=New-Object System.Drawing.Bitmap($w,$h); $gfx=[System.Drawing.Graphics]::FromImage($bmp)
$hdc=$gfx.GetHdc(); $ok=[R]::PrintWindow($noteHwnd,$hdc,2)
$gfx.ReleaseHdc($hdc); $gfx.Dispose()
$bmp.Save($Out,[System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
Write-Output ("OK {0} {1}x{2}" -f $ok,$w,$h)
"""


def capture(pid, out_path):
    """Capture the note window; retry until the frame is representative (expanded
    note, not the collapsed edge-tab). A collapsed frame has almost no text rows and
    scores ~0 on text_quality, which would be a state-dependent false regression."""
    ps_path = TMP / "taste_referee_capture.ps1"
    ps_path.write_text(CAPTURE_PS, encoding="utf-8")
    last_out = ""
    last_rc = 0
    for attempt in range(3):
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_path),
             str(pid), str(out_path)],
            capture_output=True, timeout=30,
        )
        # Decode defensively: zh-CN PowerShell emits the system codepage (GBK), not UTF-8.
        last_out = (r.stdout or b"").decode("utf-8", errors="replace").strip()
        last_rc = r.returncode
        if last_rc != 0 or "OK" not in last_out:
            continue
        # Validate the frame: expanded note must show text. A collapsed/transparent
        # layered window reads as near-black with almost no glyph rows.
        try:
            im = Image.open(out_path)
            m = objective_metrics(im)
            if m["text_rows"] >= 15:
                return last_out, last_rc
        except Exception:  # noqa: BLE001
            pass
        # Not representative — wait and re-capture (window may still be settling).
        time.sleep(1.5)
    # Last-resort: return whatever we got, but flag it used a retry.
    return last_out + " (RETRIED=3)", last_rc


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", help="path to a screenshot to score")
    ap.add_argument("--capture", type=int, metavar="PID", help="capture live note window for the given pid")
    ap.add_argument("--out", default=str(TMP / "dn_taste_referee.png"), help="capture output path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rubric-only", action="store_true", help="print the rubric template for a human/LLM judge")
    args = ap.parse_args()

    if args.rubric_only:
        print(json.dumps({"public": PUBLIC_RUBRIC, "hidden": HIDDEN_RUBRIC,
                          "weights": RUBRIC_WEIGHTS, "note": HIDDEN_NOTE}, ensure_ascii=False, indent=2))
        return

    if args.capture:
        out, rc = capture(args.capture, args.out)
        print(out)
        if rc != 0 or "OK" not in str(out):
            print("CAPTURE_FAILED")
            return
        args.png = args.out

    if not args.png:
        print("Provide --png <file> or --capture <pid>. Use --rubric-only for the rubric.")
        return

    if not HAS_PIL:
        print("PIL not installed — cannot score pixels. pip install pillow.")
        return

    im = Image.open(args.png)
    m = objective_metrics(im)
    obj = objective_scores(m)
    total_w = 0.0
    total = 0.0
    for k, val in obj.items():
        w = RUBRIC_WEIGHTS.get(k, 0.0)
        if w == 0:
            continue
        total += w * val
        total_w += w
    objective_total = total / total_w if total_w else 0.0

    result = {
        "referee": "DesktopNote perception referee",
        "png": args.png,
        "objective_subscore": round(objective_total, 1),
        "objective_metrics": m,
        "objective_breakdown": obj,
        "aesthetic": {
            "status": "NEEDS_HUMAN_OR_LLM_JUDGE",
            "public_rubric": PUBLIC_RUBRIC,
            "hidden_rubric": HIDDEN_RUBRIC,
        },
        "note": "objective_subscore is the hard-to-game floor. The aesthetic/rubric "
                "portion must be assigned by a judge literally LOOKING at the image; "
                "feeding canned scores here is worthless.",
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"DesktopNote PERCEPTION sub-score  {objective_total:.1f} / 100  (objective, pixel-derived)")
    print("=" * 60)
    print(f"image: {m['width']}x{m['height']}")
    print(f"background: {m['background']}  (off-black OK, literal #000000 depth loss)")
    print(f"background-is-pure-black: {m['bg_is_pure_black']}   violet/chrome accents: {m['violet_accents']}")
    print(f"text rows: {m['text_rows']}   accent-bar rows: {m['accent_bar_rows']}")
    for k, v in obj.items():
        print(f"  {k:<20} {v:>5.0f}/100")
    print("\nAESTHETIC rubric: needs a human/LLM judge looking at the image.")
    print("Run with --json for the full rubric + weights, or --rubric-only for the template.")


HIDDEN_NOTE = ("PUBLIC items tell an agent what is judged (so it can aim). HIDDEN items are "
               "held out by the judge and NOT published to the agent, so it cannot rehearse "
               "against the full rubric. The judge applies both; only the judge knows the hidden set.")

if __name__ == "__main__":
    main()
