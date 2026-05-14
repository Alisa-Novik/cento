#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "cento.demo_evidence.v1"
DEFAULT_DURATION_SECONDS = 15.0
MIN_DURATION_SECONDS = 10.0
MAX_DURATION_SECONDS = 30.0
DEFAULT_FPS = 15
DEFAULT_GEOMETRY = "1280x720+0,0"


class DemoEvidenceError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return re.sub(r"-{2,}", "-", text).strip("-") or "demo"


def duration_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def validate_duration(value: float) -> float:
    if value < MIN_DURATION_SECONDS or value > MAX_DURATION_SECONDS:
        raise DemoEvidenceError(
            f"demo duration must be between {duration_text(MIN_DURATION_SECONDS)} and "
            f"{duration_text(MAX_DURATION_SECONDS)} seconds"
        )
    return value


def parse_geometry(value: str) -> tuple[int, int, int, int]:
    match = re.match(r"^(\d+)x(\d+)(?:\+(-?\d+)(?:,|\+)(-?\d+))?$", value.strip())
    if not match:
        raise DemoEvidenceError("geometry must look like WIDTHxHEIGHT or WIDTHxHEIGHT+X,Y")
    width = int(match.group(1))
    height = int(match.group(2))
    x = int(match.group(3) or 0)
    y = int(match.group(4) or 0)
    if width <= 0 or height <= 0:
        raise DemoEvidenceError("geometry width and height must be positive")
    return width, height, x, y


def detect_x11_geometry() -> str:
    if shutil.which("xrandr"):
        proc = subprocess.run(["xrandr", "--current"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        match = re.search(r"current\s+(\d+)\s+x\s+(\d+)", proc.stdout)
        if match:
            return f"{match.group(1)}x{match.group(2)}+0,0"
    if shutil.which("xdpyinfo"):
        proc = subprocess.run(["xdpyinfo"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        match = re.search(r"dimensions:\s+(\d+)x(\d+)\s+pixels", proc.stdout)
        if match:
            return f"{match.group(1)}x{match.group(2)}+0,0"
    return DEFAULT_GEOMETRY


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def ffprobe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def default_run_dir(args: argparse.Namespace) -> Path:
    if args.out:
        return repo_path(args.out)

    stamp = timestamp()
    title_slug = slugify(args.task or args.title or "demo")
    if args.factory_run:
        base = repo_path(args.factory_run)
        if args.task:
            return base / "tasks" / slugify(args.task) / "evidence" / f"demo-{stamp}"
        return base / "evidence" / f"demo-{title_slug}-{stamp}"
    return ROOT / "workspace" / "runs" / "demo-evidence" / f"{title_slug}-{stamp}"


def choose_recorder(requested: str, *, dry_run: bool = False) -> str:
    if requested != "auto":
        return requested

    system = platform.system().lower()
    if system == "linux":
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wf-recorder"):
            return "wf-recorder"
        if os.environ.get("DISPLAY") and shutil.which("ffmpeg"):
            return "x11grab"
        if dry_run and shutil.which("ffmpeg"):
            return "x11grab"
        raise DemoEvidenceError("no Linux screen recorder found; install ffmpeg or wf-recorder and set DISPLAY/WAYLAND_DISPLAY")

    if system == "darwin":
        if shutil.which("ffmpeg") or dry_run:
            return "avfoundation"
        raise DemoEvidenceError("macOS demo recording requires ffmpeg with avfoundation support")

    if shutil.which("ffmpeg") or dry_run:
        return "synthetic"
    raise DemoEvidenceError(f"unsupported platform for screen recording: {platform.system()}")


def require_command(command: str, recorder: str) -> None:
    if not shutil.which(command):
        raise DemoEvidenceError(f"{recorder} recorder requires `{command}`")


def build_command(args: argparse.Namespace, video_path: Path, recorder: str) -> dict[str, Any]:
    duration = validate_duration(float(args.duration))
    fps = int(args.fps)
    if fps <= 0:
        raise DemoEvidenceError("--fps must be positive")

    if recorder == "x11grab":
        if not args.dry_run:
            require_command("ffmpeg", recorder)
            if not os.environ.get("DISPLAY"):
                raise DemoEvidenceError("x11grab recorder requires DISPLAY")
        geometry = args.geometry or detect_x11_geometry()
        width, height, x, y = parse_geometry(geometry)
        display = os.environ.get("DISPLAY", ":0")
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "x11grab",
            "-draw_mouse",
            "1",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            f"{display}+{x},{y}",
            "-t",
            duration_text(duration),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        return {"recorder": recorder, "command": command, "geometry": geometry, "display": display}

    if recorder == "wf-recorder":
        if not args.dry_run:
            require_command("wf-recorder", recorder)
            if not os.environ.get("WAYLAND_DISPLAY"):
                raise DemoEvidenceError("wf-recorder requires WAYLAND_DISPLAY")
        command = ["wf-recorder", "--file", str(video_path), "--framerate", str(fps)]
        return {
            "recorder": recorder,
            "command": command,
            "duration_controller": "cento_terminate_after_duration",
            "display": os.environ.get("WAYLAND_DISPLAY", ""),
        }

    if recorder == "avfoundation":
        if not args.dry_run:
            require_command("ffmpeg", recorder)
        input_name = args.avfoundation_input or "Capture screen 0"
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "avfoundation",
            "-framerate",
            str(fps),
            "-capture_cursor",
            "1",
            "-i",
            input_name,
            "-t",
            duration_text(duration),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        return {"recorder": recorder, "command": command, "display": input_name}

    if recorder == "synthetic":
        if not args.dry_run:
            require_command("ffmpeg", recorder)
        geometry = args.geometry or DEFAULT_GEOMETRY
        width, height, _x, _y = parse_geometry(geometry)
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={width}x{height}:rate={fps}",
            "-t",
            duration_text(duration),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        return {"recorder": recorder, "command": command, "geometry": geometry, "display": "synthetic-testsrc"}

    raise DemoEvidenceError(f"unknown recorder: {recorder}")


def run_command(plan: dict[str, Any], duration: float) -> dict[str, Any]:
    command = list(plan["command"])
    started = time.monotonic()
    if plan["recorder"] == "wf-recorder":
        proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=duration)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate(timeout=5)
        elapsed = time.monotonic() - started
        return {"returncode": proc.returncode, "stdout": stdout[-4000:], "stderr": stderr[-4000:], "elapsed_seconds": elapsed}

    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=duration + 30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": (exc.stdout or "")[-4000:],
            "stderr": (exc.stderr or f"timed out after {duration + 30:.1f}s")[-4000:],
            "elapsed_seconds": time.monotonic() - started,
            "timed_out": True,
        }
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "elapsed_seconds": time.monotonic() - started,
    }


def write_summary(run_dir: Path, receipt: dict[str, Any]) -> Path:
    summary = run_dir / "summary.md"
    artifacts = receipt.get("artifacts", {})
    lines = [
        "# Demo Evidence",
        "",
        f"- Status: `{receipt.get('status', 'unknown')}`",
        f"- Title: {receipt.get('title') or 'demo'}",
        f"- Created: `{receipt.get('created_at')}`",
        f"- Recorder: `{receipt.get('recorder')}`",
        f"- Requested duration: `{receipt.get('duration_seconds_requested')}` seconds",
    ]
    measured = receipt.get("duration_seconds_measured")
    if measured is not None:
        lines.append(f"- Measured duration: `{measured}` seconds")
    if receipt.get("factory_run"):
        lines.append(f"- Factory run: `{receipt['factory_run']}`")
    if receipt.get("task"):
        lines.append(f"- Task: `{receipt['task']}`")
    if receipt.get("worker"):
        lines.append(f"- Worker: `{receipt['worker']}`")
    lines.extend(
        [
            f"- Video: `{artifacts.get('video', '')}`",
            f"- Receipt: `{artifacts.get('receipt', '')}`",
            "",
            "## Notes",
            "",
        ]
    )
    notes = receipt.get("notes") or []
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- none")
    lines.extend(["", "## Verification", "", f"`cento demo-evidence verify {display_path(run_dir)}`"])
    if receipt.get("planned_command"):
        lines.extend(["", "## Planned Command", "", "```bash", receipt["planned_command"], "```"])
    summary.write_text("\n".join(lines).rstrip() + "\n")
    return summary


def base_receipt(args: argparse.Namespace, run_dir: Path, video_path: Path, recorder: str, plan: dict[str, Any]) -> dict[str, Any]:
    receipt_path = run_dir / "receipt.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "planned",
        "created_at": now_iso(),
        "title": args.title,
        "factory_run": args.factory_run or "",
        "task": args.task or "",
        "worker": args.worker or "",
        "tags": args.tag or [],
        "notes": args.notes or [],
        "duration_seconds_requested": float(args.duration),
        "duration_window_seconds": {"min": MIN_DURATION_SECONDS, "max": MAX_DURATION_SECONDS},
        "fps": int(args.fps),
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "recorder": recorder,
        "display": plan.get("display", ""),
        "geometry": plan.get("geometry", ""),
        "planned_command": shlex.join(plan["command"]),
        "artifacts": {
            "run_dir": display_path(run_dir),
            "video": display_path(video_path),
            "receipt": display_path(receipt_path),
            "summary": display_path(run_dir / "summary.md"),
        },
    }


def write_receipt(run_dir: Path, receipt: dict[str, Any]) -> Path:
    path = run_dir / "receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def command_record(args: argparse.Namespace) -> int:
    validate_duration(float(args.duration))
    run_dir = default_run_dir(args)
    run_dir.mkdir(parents=True, exist_ok=True)
    video_path = run_dir / args.video_name
    recorder = choose_recorder(args.recorder, dry_run=args.dry_run)
    plan = build_command(args, video_path, recorder)
    receipt = base_receipt(args, run_dir, video_path, recorder, plan)

    if args.dry_run:
        receipt.update({"status": "dry_run", "ok": True, "message": "recording command planned; video was not captured"})
        write_summary(run_dir, receipt)
        write_receipt(run_dir, receipt)
        print_result(receipt, args.json)
        return 0

    result = run_command(plan, float(args.duration))
    measured = ffprobe_duration(video_path)
    receipt["duration_seconds_measured"] = measured
    receipt["recording"] = result

    if result["returncode"] == 0 and video_path.exists() and video_path.stat().st_size > 0:
        receipt.update(
            {
                "status": "passed",
                "ok": True,
                "message": "demo captured",
                "video_bytes": video_path.stat().st_size,
                "video_sha256": sha256_file(video_path),
            }
        )
    else:
        receipt.update({"status": "failed", "ok": False, "message": "recording command failed or produced no video"})

    write_summary(run_dir, receipt)
    write_receipt(run_dir, receipt)
    print_result(receipt, args.json)
    return 0 if receipt.get("ok") else 1


def receipt_for_path(path_value: str | None) -> Path:
    if path_value:
        path = repo_path(path_value)
        if path.is_dir():
            return path / "receipt.json"
        return path

    base = ROOT / "workspace" / "runs" / "demo-evidence"
    receipts = sorted(base.glob("*/receipt.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not receipts:
        raise DemoEvidenceError("no demo evidence receipts found under workspace/runs/demo-evidence")
    return receipts[0]


def verify_receipt(receipt_path: Path) -> dict[str, Any]:
    if not receipt_path.exists():
        return {"ok": False, "receipt": display_path(receipt_path), "checks": [{"name": "receipt exists", "ok": False}]}

    receipt = json.loads(receipt_path.read_text())
    artifacts = receipt.get("artifacts") or {}
    video_value = artifacts.get("video") or ""
    video_path = repo_path(video_value) if video_value else receipt_path.parent / "demo.mp4"
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("receipt status passed", receipt.get("status") == "passed", str(receipt.get("status", "")))
    add("video exists", video_path.exists(), display_path(video_path))
    add("video nonempty", video_path.exists() and video_path.stat().st_size > 0, str(video_path.stat().st_size if video_path.exists() else 0))

    measured = ffprobe_duration(video_path)
    if measured is None:
        measured = receipt.get("duration_seconds_measured")
    if measured is None:
        add("duration readable", False, "ffprobe duration unavailable")
    else:
        in_window = MIN_DURATION_SECONDS <= float(measured) <= MAX_DURATION_SECONDS + 0.75
        add("duration in 10-30s window", in_window, duration_text(float(measured)))

    expected_hash = receipt.get("video_sha256")
    if expected_hash and video_path.exists():
        actual_hash = sha256_file(video_path)
        add("sha256 matches receipt", actual_hash == expected_hash, actual_hash)
    elif expected_hash:
        add("sha256 matches receipt", False, "video missing")

    ok = all(item["ok"] for item in checks)
    return {
        "ok": ok,
        "receipt": display_path(receipt_path),
        "video": display_path(video_path),
        "checks": checks,
        "summary": "demo evidence verified" if ok else "demo evidence verification failed",
    }


def command_verify(args: argparse.Namespace) -> int:
    result = verify_receipt(receipt_for_path(args.path))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["summary"])
        for check in result["checks"]:
            marker = "PASS" if check["ok"] else "FAIL"
            detail = f" - {check['detail']}" if check.get("detail") else ""
            print(f"{marker} {check['name']}{detail}")
    return 0 if result["ok"] else 1


def command_status(args: argparse.Namespace) -> int:
    receipt_path = receipt_for_path(args.path)
    receipt = json.loads(receipt_path.read_text())
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"{receipt.get('status', 'unknown')} {receipt.get('title', '')}")
        print(f"run: {receipt.get('artifacts', {}).get('run_dir', display_path(receipt_path.parent))}")
        print(f"video: {receipt.get('artifacts', {}).get('video', '')}")
        print(f"receipt: {display_path(receipt_path)}")
    return 0 if receipt.get("status") == "passed" else 1


def print_result(receipt: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return
    print(f"demo evidence {receipt.get('status')}: {receipt.get('message', '')}")
    print(f"run: {receipt.get('artifacts', {}).get('run_dir', '')}")
    print(f"video: {receipt.get('artifacts', {}).get('video', '')}")
    print(f"receipt: {receipt.get('artifacts', {}).get('receipt', '')}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record short 10-30 second demo videos as Cento evidence.")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="Record a short demo clip and receipt.")
    record.add_argument("--title", default="Short demo evidence", help="Human-readable evidence title.")
    record.add_argument("--duration", type=float, default=DEFAULT_DURATION_SECONDS, help="Clip length in seconds; must be 10-30.")
    record.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Capture frame rate.")
    record.add_argument("--geometry", help="Capture region as WIDTHxHEIGHT+X,Y. Defaults to detected screen size.")
    record.add_argument("--out", help="Output run directory. Defaults to workspace/runs/demo-evidence or Factory evidence path.")
    record.add_argument("--factory-run", help="Factory run directory, such as workspace/runs/factory/<run>.")
    record.add_argument("--task", help="Factory task id or worker task id.")
    record.add_argument("--worker", help="Worker id or local agent label.")
    record.add_argument("--notes", action="append", default=[], help="Evidence note. Can be passed multiple times.")
    record.add_argument("--tag", action="append", default=[], help="Evidence tag. Can be passed multiple times.")
    record.add_argument("--video-name", default="demo.mp4", help="Video file name inside the run directory.")
    record.add_argument(
        "--recorder",
        choices=["auto", "x11grab", "wf-recorder", "avfoundation", "synthetic"],
        default="auto",
        help="Recorder backend. Synthetic is only for smoke tests, not product evidence.",
    )
    record.add_argument("--avfoundation-input", help="macOS ffmpeg avfoundation input name.")
    record.add_argument("--dry-run", action="store_true", help="Write receipt and summary without recording video.")
    record.add_argument("--json", action="store_true", help="Print JSON receipt.")
    record.set_defaults(func=command_record)

    verify = sub.add_parser("verify", help="Verify a demo evidence receipt and video.")
    verify.add_argument("path", nargs="?", help="Run directory or receipt.json. Defaults to latest workspace/runs/demo-evidence receipt.")
    verify.add_argument("--json", action="store_true", help="Print JSON verification result.")
    verify.set_defaults(func=command_verify)

    status = sub.add_parser("status", help="Print a demo evidence receipt status.")
    status.add_argument("path", nargs="?", help="Run directory or receipt.json. Defaults to latest workspace/runs/demo-evidence receipt.")
    status.add_argument("--json", action="store_true", help="Print full JSON receipt.")
    status.set_defaults(func=command_status)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return args.func(args)
    except DemoEvidenceError as exc:
        print(f"demo-evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
