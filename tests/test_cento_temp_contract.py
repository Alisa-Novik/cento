import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _temp_tool() -> dict:
    payload = json.loads((ROOT / "data" / "tools.json").read_text(encoding="utf-8"))
    for tool in payload["tools"]:
        if tool["id"] == "temp":
            return tool
    raise AssertionError("temp tool is not registered")


def test_temp_registry_is_one_command_clipboard_bridge() -> None:
    tool = _temp_tool()

    assert tool["entrypoint"] == "./scripts/cento_temp.sh"
    assert tool["commands"] == ["cento temp run"]
    assert "COPY_FILE" in "\n".join(tool["notes"])


def test_temp_docs_and_routes_do_not_reintroduce_ids() -> None:
    checked_paths = [
        ROOT / "docs" / "temp-commands.md",
        ROOT / "skills" / "codex" / "cento-native" / "SKILL.md",
        ROOT / "skills" / "codex" / "cento-native" / "references" / "routing.md",
        ROOT / "skills" / "claude-code" / "cento-native.md",
    ]
    banned = [
        "cento temp add",
        "cento temp show",
        "cento temp list",
        "cento temp remove",
        "cento temp run ID",
        "cento temp run openai-key",
    ]

    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for phrase in banned:
            assert phrase not in text, f"{path} still contains {phrase}"


def test_temp_wrapper_rejects_variations_before_copying() -> None:
    script = ROOT / "scripts" / "cento_temp.sh"
    for args in ([], ["show"], ["run", "extra"]):
        result = subprocess.run(
            ["bash", str(script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 2
        assert "Usage: cento temp run" in result.stderr
