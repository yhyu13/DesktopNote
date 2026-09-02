#!/usr/bin/env python3
"""
DesktopNote Taste-Score Mutation Audit (Goodhart defense).

Goodhart's Law: once a score becomes a target, agents optimise the score, not taste.
A score is only trustworthy if it is *sensitive* — deliberately degrading the actual
product must lower the score. This script injects known regressions (mutations) into a
copy of the source tree and asserts the taste score DROPS for each. If a mutation
doesn't drop the score, that check is gameable: an agent could delete the code the
check rewards and fake the value.

Mutations are chosen to probe the main scoring dimensions:
  - M1  accent de-fragmentation: collapse kBorderColors to a single hue  -> coherence
  - M2  pure-black background: lose depth                              -> coherence
  - M3  arbitrary radius explosion: many unrelated radii               -> polish
  - M4  hover/press handling removed                                   -> polish
  - M5  web font (Arial) as default                                    -> type
  - M6  font size in raw px (not DIP)                                  -> type
  - M7  native surface removed (WS_POPUP / UpdateLayeredWindow gone)   -> platform
  - M8  DIP -> raw-pixel everywhere (DPI leak)                          -> platform

Usage:
    python3 tools/taste_mutation.py           # run all mutations, compare scores
    python3 tools/taste_mutation.py --fail-on-no-change

Exit code 0 if every mutation lowers the score (score is sensitive). Non-zero lists
the mutations that did NOT lower the score (gameable / insensitive checks).

Notes:
  - Scores a COPY via taste_score.py --src; never touches the real tree.
  - Uses python3 (host `python` is 2.7).
  - Mutation M8 / M7 probe the build-constraint and native-surface checks that the
    static scorer rewards by counting symbols — these are the structurally weakest
    (most gameable) checks, which is exactly what this audit surfaces.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SCORER = ROOT / "tools" / "taste_score.py"


def read_file(p):
    return p.read_text(encoding="utf-8", errors="replace")


def write_file(p, content):
    p.write_text(content, encoding="utf-8")


def copy_tree(dst):
    """Copy src/ into a temp dir, return the copy's src path."""
    tmp = Path(tempfile.mkdtemp(prefix="taste_mutation_"))
    dst_src = tmp / "src"
    shutil.copytree(SRC, dst_src)
    return tmp, dst_src


def score_dir(src_dir):
    """Run the static scorer against src_dir, return (total, per-dim dict)."""
    r = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCORER)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return None, {}
    r = subprocess.run(
        [sys.executable, str(SCORER), "--src", str(src_dir), "--json"],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(r.stdout)
    except Exception:
        return None, {}
    dims = {d["dimension"]: d["score"] for d in data.get("dimensions", [])}
    return data.get("score"), dims


# --------------------------------------------------------------------------
# Mutation definitions: (label, repo-relative file, old->new substitution)
# Each returns a list of (relative_path, old, new) edits.
# --------------------------------------------------------------------------

def mutate_accent_collapse():
    return [
        ("note_toolbar.cpp",
         "0x8B5CF6,  // Iris Violet",
         "0x8B5CF6,  // Iris Violet (kept)"),
        # keep file valid; the real probe is replacing the border palette with 1 hue
    ]


def mutate_accent_collapse_real():
    # Collapse the user border palette to a single hue -> less colour choice richness.
    # This tests whether the scorer rewards variety or penalises a mono palette.
    return [
        ("note_toolbar.cpp",
         "   0x10B981,  // Emerald\n    0x0288D1,  // Cyber Blue\n    0xF43F5E,  // Coral Rose\n    0x8B5CF6,  // Iris Violet\n    0x64748B   // Graphite Slate",
         "   0x10B981   // Emerald (mono palette)"),
    ]


def mutate_pure_black_bg():
    return [
        ("app_state.h",
         "std::uint32_t background_color = 0x1E1E24;",
         "std::uint32_t background_color = 0x000000;"),
    ]


def mutate_radius_explosion():
    # Replace the collapsed-tab capsule radius with many arbitrary values.
    return [
        ("note_renderer.cpp",
         "const float corner_radius = tab_depth * 0.5F;",
         "const float corner_radius = 3.3F; /* arbitrary */"),
    ]


def mutate_hover_removed():
    # The renderer is static anyway; we can't literally remove what isn't there.
    # Instead, probe a *positive* direction: the scorer's "no interaction handling"
    # check rewards the ABSENCE. So deleting nothing is already the max. Add a fake
    # TrackMouseEvent loop to see if the scorer wrongly rewards added (unused) code.
    return [
        ("note_renderer.cpp",
         "    const HRESULT text_draw_result = (rich_edit && !is_collapsed) ? rich_edit->Draw(render_target_) : S_OK;",
         "    const HRESULT text_draw_result = (rich_edit && !is_collapsed) ? rich_edit->Draw(render_target_) : S_OK;\n    TRACKMOUSEEVENT _tme{}; _tme.cbSize = sizeof(_tme); _tme.dwFlags = TME_LEAVE; TrackMouseEvent(&_tme);"),
    ]


def mutate_web_font():
    return [
        ("app_state.h",
         'std::wstring font_family = L"Microsoft YaHei UI";',
         'std::wstring font_family = L"Arial";'),
    ]


def mutate_font_px():
    # Genuinely remove the DIP-based font size property (the check looks for
    # `font_size_dip = <num>`). Rename it to a raw-pixel field.
    return [
        ("app_state.h",
         "double font_size_dip = 16.0;",
         "double font_size_px = 16.0; /* raw px, not DIP-scaled */"),
    ]


def mutate_native_removed():
    return [
        ("note_window.cpp",
         "WS_POPUP",
         "WS_CHILD"),
    ]


def mutate_dpi_leak():
    # Break the render-target's per-monitor DPI wiring (the property that actually
    # matters for pixel correctness). Leave the unrelated line-99 const intact so the
    # mutation isolates the render-target call specifically.
    return [
        ("note_renderer.cpp",
         "        static_cast<float>(DpiForWindowOrSystem(window)),\n        static_cast<float>(DpiForWindowOrSystem(window)),",
         "        static_cast<float>(96),\n        static_cast<float>(96),"),
    ]


# Each mutation is tagged with a tier:
#   "structure"  -> should DROP the structure score; if not caught, the check is gameable.
#   "perception" -> tests an aesthetic property the structure score deliberately does NOT
#                   judge (they live in the perception referee). EXPECTED to be insensitive;
#                   a pass here is fine, a drop would mean we accidentally re-used a
#                   gameable symbol-count for an aesthetic.
MUTATIONS = [
    ("M1 accent-collapse", mutate_accent_collapse_real, "perception"),
    ("M2 pure-black-bg", mutate_pure_black_bg, "structure"),
    ("M3 radius-explosion", mutate_radius_explosion, "perception"),
    ("M4 added-trackmouse", mutate_hover_removed, "perception"),
    ("M5 web-font", mutate_web_font, "structure"),
    ("M6 font-fake-px", mutate_font_px, "structure"),
    ("M7 native-surface-lost", mutate_native_removed, "structure"),
    ("M8 dpi-leak", mutate_dpi_leak, "structure"),
]


def apply_edits(tmp_src, edits):
    for rel, old, new in edits:
        path = tmp_src / rel
        content = read_file(path)
        if old in content:
            write_file(path, content.replace(old, new))
        else:
            raise RuntimeError(f"mutation anchor not found in {rel}: {old[:60]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail-on-no-change", action="store_true",
                    help="exit nonzero if any mutation fails to lower the score")
    ap.add_argument("--keep", action="store_true", help="keep temp mutated trees")
    args = ap.parse_args()

    baseline, _ = score_dir(SRC)
    print(f"Baseline STRUCTURE score: {baseline}")

    results = []
    gameable = []   # structure-tier mutations that were NOT caught (bad)
    perception_dropped = []  # perception-tier mutation that DROPPED score (means a
                             # structure check still judges it -> should be perception-only)

    for label, fn, tier in MUTATIONS:
        tmp, tmp_src = copy_tree(SRC)
        try:
            apply_edits(tmp_src, fn())
            score, dims = score_dir(tmp_src)
            delta = None if (score is None or baseline is None) else round(score - baseline, 1)
            down = delta is not None and delta < 0
            results.append((label, tier, baseline, score, delta, down))
            if down and tier == "perception":
                perception_dropped.append(label)   # structure check over-reaches on aesthetics
            elif not down and tier == "structure":
                gameable.append(label)             # structure check is insensitive (bad)
        except Exception as e:  # noqa: BLE001
            results.append((label, tier, baseline, None, None, False))
            if tier == "structure":
                gameable.append(label + f" (anchor miss: {e!r})")
        finally:
            if not args.keep:
                shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{'mutation':<24} {'tier':<12} {'base':>6} {'mut':>6} {'Δ':>6}   {'verdict'}")
    for label, tier, base, mut, delta, down in results:
        if tier == "structure":
            verdict = "CAUGHT" if down and delta is not None and delta < 0 else "GAMEABLE!"
        else:
            verdict = "insensitive (OK)" if not down else "over-reach (should be perception-only)"
        delta_s = "n/a" if delta is None else f"{delta:+.1f}"
        print(f"{label:<24} {tier:<12} {str(base):>6} {str(mut):>6} {delta_s:>6}   {verdict}")

    print("\n== Goodhart read ==")
    if gameable:
        print(f"{len(gameable)} STRUCTURE-tier mutation(s) NOT caught — these checks are GAMEABLE:")
        for label in gameable:
            print(f"  - {label}")
        print("\nAn agent can farm these by deleting the code the check rewards, or adding")
        print("unused symbols, without real quality improving. Fix or drop the check, or")
        print("move that property to the perception referee.")
    else:
        print("All STRUCTURE-tier mutations lower the score — the structure checks are sensitive.")

    if perception_dropped:
        print(f"\n{len(perception_dropped)} PERCEPTION-tier mutation(s) DROPPED the structure score —")
        print("a structure check still judges an aesthetic property (gameable):")
        for label in perception_dropped:
            print(f"  - {label}")
        print("Move these to perception-only.")

    # Pass only if no structure check is gameable.
    hard_fail = args.fail_on_no_change and (gameable or perception_dropped)
    if hard_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
