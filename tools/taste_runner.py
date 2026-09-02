#!/usr/bin/env python3
"""
DesktopNote Taste Overnight-Competition Runner.

Ties the whole Goodhart-resistant pipeline into ONE command that an agent lane
(or a cron job) can invoke and get a single comparable result:

  1. BUILD+TEST gate        (structure)   — hard fail if red
  2. STRUCTURE score        (correctness) — 0-100, static
  3. MUTATION audit         (anti-gaming) — must be sensitive or the run is invalid
  4. CAPTURE + PERCEPTION   (taste)       — live screenshot -> objective sub-score
                                           + aesthetic rubric for a human/LLM judge

Optimal overnight loop: agents iterate to raise (4) perception WITHOUT breaking
(1)(2)(3). The structure score is a gate, not the prize.

Usage:
  python3 tools/taste_runner.py                    # full pipeline
  python3 tools/taste_runner.py --no-build         # skip build gate
  python3 tools/taste_runner.py --png <file>       # score an existing screenshot
  python3 tools/taste_runner.py --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(os.environ.get("TEMP", "/tmp"))
CAPTURED = TMP / "dn_runner_capture.png"


def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=240)


def structure_score(do_build, do_mutation):
    """Return (score, detail). Build gate applies if do_build."""
    cmd = [sys.executable, str(ROOT / "tools" / "taste_score.py"), "--json"]
    if do_build:
        cmd.append("--build")
    r = run(cmd)
    try:
        data = json.loads(r.stdout)
    except Exception:
        return None, {"error": "structure parse failed", "raw": r.stdout[:300]}
    detail = {"score": data.get("score"), "gated": data.get("gated"),
              "dims": {d["dimension"]: d["score"] for d in data.get("dimensions", [])}}
    if do_mutation:
        mr = run([sys.executable, str(ROOT / "tools" / "taste_mutation.py")])
        detail["mutation"] = mr.stdout.strip()
    return data.get("score"), detail


def perception_score(png):
    r = run([sys.executable, str(ROOT / "tools" / "taste_referee.py"), "--png", png, "--json"])
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": "perception parse failed", "raw": r.stdout[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true", help="skip the build+ctest gate")
    ap.add_argument("--png", help="score an existing screenshot instead of capturing")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--data-dir", help="isolated data dir for the capture instance")
    args = ap.parse_args()

    result = {"project": "DesktopNote"}

    # 1+2+3: structure + (build gate) + mutation
    s, sdetail = structure_score(not args.no_build, do_mutation=True)
    result["structure_score"] = s
    if args.json:
        result["structure_detail"] = sdetail

    # 4: perception (capture or given png)
    png = args.png
    if not png:
        # capture live app; spawn an isolated instance. DesktopNote is single-instance
        # (named mutex), so a stale exe would swallow the signal and `Get-Process` can
        # return multiple PIDs (int() crash). Kill first, launch one, then take the
        # NEWEST DesktopNote PID and guard the parse.
        data_env = args.data_dir or os.path.join(os.environ.get("LOCALAPPDATA", ""), "DesktopNoteTasteReferee")
        launch = ["powershell", "-NoProfile", "-Command",
                  f"Stop-Process -Name DesktopNote -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800; "
                  f"$env:DESKTOPNOTE_DATA_DIR='{data_env}'; Start-Process -FilePath '{ROOT}/build/msvc-release/Release/DesktopNote.exe' -WorkingDirectory '{ROOT}'; "
                  f"Start-Sleep -Seconds 2; (Get-Process DesktopNote | Sort-Object StartTime -Descending | Select-Object -First 1).Id"]
        lr = run(launch)
        pids = re.findall(r"\d+", (lr.stdout or ""))
        pid = int(pids[0]) if pids else None
        result["launch_out"] = (lr.stdout or "").strip()
        time.sleep(1)
        if pid is None:
            result["capture"] = {"ok": False, "out": "no DesktopNote pid after launch"}
            png = None
        else:
            from importlib import util
            spec = util.spec_from_file_location("tr", str(ROOT / "tools" / "taste_referee.py"))
            tr = util.module_from_spec(spec)
            spec.loader.exec_module(tr)
            out, rc = tr.capture(int(pid), str(CAPTURED))
            if rc == 0 and "OK" in out:
                png = str(CAPTURED)
            else:
                result["capture"] = {"ok": False, "out": out, "pid": pid}

    if png:
        perc = perception_score(png)
        result["perception"] = perc
        # composite: structure is a gate; perception is the competition metric.
        if s is not None and s < 100 and not args.no_build and result.get("structure_detail", {}).get("gated"):
            result["verdict"] = "REJECT (build/structure gate below par)"
        elif perc.get("objective_subscore") is not None:
            result["verdict"] = "ACCEPT (structure gate clean; compete on perception)"
        else:
            result["verdict"] = "INCOMPLETE (no perception score)"
    else:
        perc = None
        result["verdict"] = "INCOMPLETE (no screenshot captured — needs desktop session)"

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 62)
    print("DesktopNote TASTE RUNNER")
    print("=" * 62)
    print(f"structure score : {s}")
    print(f"perception obj  : {perc.get('objective_subscore') if perc else 'n/a'}")
    print(f"verdict         : {result.get('verdict')}")
    print("=" * 62)
    print("Structure = gate (correctness). Perception = the competition metric (taste).")
    print("Iterate to raise perception; never let structure regress.")


if __name__ == "__main__":
    main()
