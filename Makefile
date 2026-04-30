PYTHON ?= python3
ROOT ?= .
TARGET ?= .
NAME ?= demo-project
PATTERN ?= *
QUERY ?= TODO
DEVICE ?=
CMD ?= pwd
ARGS ?=

.PHONY: check tree index platforms inventory snapshot scaffold batch search bt-audio-doctor audio-quick-connect kitty-theme wallpaper display i3reorg dashboard preset bridge quick-help quick-help-fzf network network-tui jobs idea-board tg tui crm funnel funnel-check burp mcp scan cento redmine-e2e terminal-e2e industrial-e2e

check:
	$(PYTHON) -m py_compile scripts/agent_work.py scripts/bluetooth_audio_doctor.py scripts/cento_interactive.py scripts/cluster_job_runner.py scripts/crm_module.py scripts/dashboard_server.py scripts/funnel_check.py scripts/funnel_module.py scripts/gather_context.py scripts/idea_board_server.py scripts/industrial_focus.py scripts/industrial_panel.py scripts/industrial_status.py scripts/jobs_server.py scripts/mcp_tooling.py scripts/network_web_server.py scripts/platform_report.py scripts/scan_onepager.py scripts/tool_index.py
	go build -o workspace/tmp/cento-interactive-check ./scripts/cento_interactive.go
	go build -o workspace/tmp/cento-daily-check ./scripts/daily_tui.go
	go build -o workspace/tmp/cento-industrial-aux-tui-check ./scripts/industrial_aux_tui.go
	go build -o workspace/tmp/cento-industrial-cluster-tui-check ./scripts/industrial_cluster_tui.go
	go build -o workspace/tmp/cento-industrial-jobs-tui-check ./scripts/industrial_jobs_tui.go
	go build -o workspace/tmp/cento-network-tui-check ./scripts/network_tui.go
	go build -o workspace/tmp/telegram-tui-check ./scripts/telegram_tui.go
	$(PYTHON) -c 'import json, pathlib; json.loads(pathlib.Path("data/tools.json").read_text()); json.loads(pathlib.Path(".mcp.json").read_text())'
	$(PYTHON) scripts/funnel_check.py
	./scripts/industrial_panel_e2e.sh
	bash -n scripts/system_inventory.sh scripts/repo_snapshot.sh scripts/project_scaffold.sh scripts/batch_exec.sh scripts/search_report.sh scripts/audio_quick_connect.sh scripts/daily_tui.sh scripts/network_tui.sh scripts/network.sh scripts/jobs.sh scripts/idea_board.sh scripts/restart_discord.sh scripts/kitty_theme_manager.sh scripts/wallpaper_manager.sh scripts/display_layout_fix.sh scripts/i3reorg.sh scripts/preset.sh scripts/industrial_os_preset.sh scripts/industrial_aux_tui.sh scripts/industrial_cluster_tui.sh scripts/industrial_jobs_tui.sh scripts/industrial_panel_e2e.sh scripts/industrial_workspace.sh scripts/bridge.sh scripts/cluster.sh scripts/notify.sh scripts/redmine_workflow_e2e.sh scripts/dashboard.sh scripts/quick_help.sh scripts/quick_help_fzf.sh scripts/burp_suite_community.sh scripts/install_macos.sh scripts/install_linux.sh scripts/terminal_integration_e2e.sh scripts/cento.sh scripts/lib/common.sh
	zsh -n scripts/completion/_cento

industrial-e2e:
	./scripts/industrial_panel_e2e.sh

tree:
	find . -maxdepth 3 -not -path './.git*' | sort

index:
	$(PYTHON) scripts/tool_index.py --registry data/tools.json --output docs/tool-index.md

platforms:
	$(PYTHON) scripts/platform_report.py --registry data/tools.json --markdown --output docs/platform-support.md

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

audio-quick-connect:
	./scripts/audio_quick_connect.sh "$(DEVICE)" $(ARGS)

kitty-theme:
	./scripts/kitty_theme_manager.sh $(ARGS)

cento:
	./scripts/cento.sh $(ARGS)

wallpaper:
	./scripts/wallpaper_manager.sh $(ARGS)

display:
	./scripts/display_layout_fix.sh $(ARGS)

i3reorg:
	./scripts/i3reorg.sh $(ARGS)

dashboard:
	./scripts/dashboard_server.py $(ARGS)

preset:
	./scripts/preset.sh $(ARGS)

jobs:
	./scripts/jobs.sh $(ARGS)

bridge:
	./scripts/bridge.sh $(ARGS)

tg:
	./scripts/telegram_tui.sh $(ARGS)

tui:
	./scripts/telegram_tui.sh $(ARGS)

crm:
	$(PYTHON) scripts/crm_module.py $(ARGS)

funnel:
	$(PYTHON) scripts/funnel_module.py $(ARGS)

funnel-check:
	$(PYTHON) scripts/funnel_check.py

burp:
	./scripts/burp_suite_community.sh $(ARGS)

quick-help:
	./scripts/quick_help.sh $(ARGS)

quick-help-fzf:
	./scripts/quick_help_fzf.sh $(ARGS)

network-tui:
	./scripts/network_tui.sh $(ARGS)

network:
	./scripts/network.sh $(ARGS)

idea-board:
	./scripts/idea_board.sh $(ARGS)

mcp:
	$(PYTHON) scripts/mcp_tooling.py $(ARGS)

scan:
	$(PYTHON) scripts/scan_onepager.py --query "$(QUERY)" $(ARGS)

redmine-e2e:
	./scripts/redmine_workflow_e2e.sh $(ARGS)

terminal-e2e:
	./scripts/terminal_integration_e2e.sh $(ARGS)
