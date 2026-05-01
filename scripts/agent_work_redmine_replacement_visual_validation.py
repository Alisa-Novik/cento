#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageChops


@dataclass
class VisualCheckResult:
    name: str
    reference: Path
    captured: Path
    diff_ratio: float
    max_ratio: float
    passed: bool


def parse_viewport(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in str(value).replace("x", ",").split(",") if part.strip()]
    if len(parts) != 2:
        raise ValueError(f"invalid viewport '{value}'")
    width = int(parts[0])
    height = int(parts[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"viewport must be positive: {value}")
    return width, height


def ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing image path: {path}")


def compute_diff_ratio(reference: Path, captured: Path) -> float:
    with Image.open(reference) as ref_image_raw, Image.open(captured) as captured_image_raw:
        reference_rgb = ref_image_raw.convert("RGB")
        captured_rgb = captured_image_raw.convert("RGB")
    if reference_rgb.size != captured_rgb.size:
        reference_rgb = reference_rgb.resize(captured_rgb.size, Image.Resampling.LANCZOS)
    if captured_rgb.size == (0, 0):
        raise ValueError("captured image has zero area")
    diff = ImageChops.difference(reference_rgb, captured_rgb)
    histogram = diff.histogram()
    if not histogram:
        raise ValueError("failed to compute image diff histogram")
    if len(histogram) % 256 != 0:
        raise ValueError("unsupported histogram shape for diff computation")
    channels = len(histogram) // 256
    total = 0
    for channel_offset in range(0, len(histogram), 256):
        channel_hist = histogram[channel_offset : channel_offset + 256]
        total += sum(level * count for level, count in enumerate(channel_hist))
    width, height = captured_rgb.size
    max_total = width * height * channels * 255
    return total / max_total if max_total else 0.0


def run_check(name: str, reference: Path, captured: Path, *, max_diff_ratio: float) -> VisualCheckResult:
    ensure_exists(reference)
    ensure_exists(captured)
    diff_ratio = compute_diff_ratio(reference, captured)
    return VisualCheckResult(
        name=name,
        reference=reference,
        captured=captured,
        diff_ratio=diff_ratio,
        max_ratio=max_diff_ratio,
        passed=diff_ratio <= max_diff_ratio,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare captured list/detail screenshots against reference fixtures."
    )
    parser.add_argument("--name", required=True, help="Fixture/check label for the report.")
    parser.add_argument("--reference", required=True, help="Reference image path.")
    parser.add_argument("--captured", required=True, help="Captured screenshot path.")
    parser.add_argument("--report", required=True, help="JSON report output path.")
    parser.add_argument(
        "--max-diff-ratio",
        type=float,
        default=0.15,
        help="Maximum tolerated mean absolute per-channel diff ratio (0.0-1.0).",
    )
    parser.add_argument(
        "--fail-if-missing",
        action="store_true",
        help="Exit with failure when captured output is missing (keeps evidence clear).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reference = Path(args.reference)
    captured = Path(args.captured)
    report_path = Path(args.report)

    if args.fail_if_missing:
        for path in (reference, captured):
            if not path.exists():
                raise FileNotFoundError(f"missing image path: {path}")
    result = run_check(args.name, reference, captured, max_diff_ratio=float(args.max_diff_ratio))
    report = {
        "name": result.name,
        "reference": str(reference),
        "captured": str(captured),
        "diff_ratio": result.diff_ratio,
        "diff_percent": result.diff_ratio * 100,
        "max_diff_ratio": result.max_ratio,
        "max_diff_percent": result.max_ratio * 100,
        "passed": result.passed,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not result.passed:
        print(f"FAILED: {args.name} diff={result.diff_ratio:.6f} max={result.max_ratio:.6f}")
        return 1
    print(f"PASS: {args.name} diff={result.diff_ratio:.6f} max={result.max_ratio:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
