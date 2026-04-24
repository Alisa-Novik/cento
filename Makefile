PYTHON ?= python3
ROOT ?= .
TARGET ?= .
NAME ?= demo-project
PATTERN ?= *
QUERY ?= TODO
DEVICE ?=
CMD ?= pwd
ARGS ?=

.PHONY: check tree index inventory snapshot scaffold batch search bt-audio-doctor kitty-theme wallpaper display cento

check:
	$(PYTHON) -m py_compile scripts/bluetooth_audio_doctor.py scripts/tool_index.py
	$(PYTHON) -c 'import json, pathlib; json.loads(pathlib.Path("data/tools.json").read_text())'
	bash -n scripts/system_inventory.sh scripts/repo_snapshot.sh scripts/project_scaffold.sh scripts/batch_exec.sh scripts/search_report.sh scripts/kitty_theme_manager.sh scripts/wallpaper_manager.sh scripts/display_layout_fix.sh scripts/cento.sh scripts/lib/common.sh

tree:
	find . -maxdepth 3 -not -path './.git*' | sort

index:
	$(PYTHON) scripts/tool_index.py --registry data/tools.json --output docs/tool-index.md

inventory:
	./scripts/system_inventory.sh $(ARGS)

snapshot:
	./scripts/repo_snapshot.sh --target "$(TARGET)" $(ARGS)

scaffold:
	./scripts/project_scaffold.sh --path "$(ROOT)/$(NAME)" $(ARGS)

batch:
	./scripts/batch_exec.sh --root "$(ROOT)" --pattern "$(PATTERN)" --command "$(CMD)" $(ARGS)

search:
	./scripts/search_report.sh --query "$(QUERY)" --root "$(ROOT)" $(ARGS)

bt-audio-doctor:
	$(PYTHON) scripts/bluetooth_audio_doctor.py "$(DEVICE)" $(ARGS)

kitty-theme:
	./scripts/kitty_theme_manager.sh $(ARGS)

cento:
	./scripts/cento.sh $(ARGS)

wallpaper:
	./scripts/wallpaper_manager.sh $(ARGS)

display:
	./scripts/display_layout_fix.sh $(ARGS)
