#!/usr/bin/env python3
from __future__ import annotations

import industrial_focus


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    targets = industrial_focus.TARGET_CLASSES
    graph = industrial_focus.VISUAL_GRAPH

    assert_true("cento-industrial-pet" in targets, "focus targets must include the pet pane")
    assert_true("cento-industrial-jobs" in targets, "focus targets should keep legacy jobs fallback")
    assert_true(graph["down"]["discord"] == "cento-industrial-pet", "discord down should focus pet")
    assert_true(graph["right"]["cento-industrial-pet"] == "cento-industrial-cluster", "pet right should focus cluster")
    assert_true(graph["up"]["cento-industrial-pet"] == "discord", "pet up should focus discord")
    assert_true(graph["left"]["cento-industrial-cluster"] == "cento-industrial-pet", "cluster left should focus pet")
    assert_true(graph["right"]["cento-industrial-jobs"] == "cento-industrial-cluster", "legacy jobs right fallback")
    assert_true(graph["up"]["cento-industrial-jobs"] == "discord", "legacy jobs up fallback")
    print("industrial focus contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
