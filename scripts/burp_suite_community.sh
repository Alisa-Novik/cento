#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/common.sh"

APP_NAME="Burp Suite Community"
PORTSWIGGER_DOWNLOAD_BASE="https://portswigger.net/burp/releases/download?product=community"
DEFAULT_HOME="${CENTO_BURP_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/cento/burp}"
DEFAULT_BIN_DIR="${CENTO_BURP_BIN_DIR:-$HOME/.local/bin}"
DOWNLOAD_DIR="$DEFAULT_HOME/downloads"
INSTALL_DIR="$DEFAULT_HOME/current"
PID_FILE="$DEFAULT_HOME/burp.pid"
LOG_FILE="$DEFAULT_HOME/burp.log"
META_FILE="$DEFAULT_HOME/install.env"

usage() {
    cat <<'USAGE'
Usage: cento burp COMMAND [options]

Commands:
  download       Download the latest official Burp Suite Community artifact
  setup          Download the JAR and create a local launcher
  controller     Control the local Burp process
  start          Alias for: controller start
  run            Run Burp in the foreground
  stop           Stop the background Burp process started by controller
  restart        Restart the background Burp process
  status         Show installed artifact and process status
  logs           Follow or print the controller log
  paths          Print managed paths
  docs           Print this tool's documentation

Download/setup options:
  --type jar|linux      Artifact type. Default: jar
  --force               Re-download or replace launcher files
  --output-dir DIR      Download directory. Default: ~/.local/share/cento/burp/downloads
  --install-dir DIR     Setup directory. Default: ~/.local/share/cento/burp/current
  --bin-dir DIR         Launcher directory. Default: ~/.local/bin

Controller options:
  --project-file PATH   Pass a Burp project file to Java
  --config-file PATH    Pass a Burp user config file to Java
  --use-defaults        Skip initial project/config prompts where Burp supports it
  --java-opts STRING    Extra JVM options before -jar
  --                  Forward remaining args directly to Burp

Examples:
  cento burp download
  cento burp download --type linux
  cento burp setup
  cento burp controller start --use-defaults
  cento burp run -- --help
  cento burp status
USAGE
}

docs() {
    cat <<'DOCS'
# Burp Suite Community

`cento burp` is a thin local controller around official PortSwigger Burp Suite
Community downloads. The default path uses the official Community JAR because it
is easy to automate and can be launched through a generated shell wrapper.

Managed state:

- downloads: `~/.local/share/cento/burp/downloads`
- active setup: `~/.local/share/cento/burp/current`
- launcher: `~/.local/bin/burp-community`
- process metadata: `~/.local/share/cento/burp/burp.pid`
- log: `~/.local/share/cento/burp/burp.log`

Primary workflow:

```bash
cento burp setup
cento burp controller start --use-defaults
cento burp status
cento burp stop
```

`download --type linux` fetches the official Linux installer for manual or later
automation use. The setup command intentionally uses the JAR path by default so
it does not need installer UI automation or privileged writes.

Burp Suite is a GUI application. `controller start` starts it in the background
and records a PID; `run` keeps it attached to the current terminal.
DOCS
}

download_url_for_type() {
    case "$1" in
        jar)
            printf '%s&type=Jar\n' "$PORTSWIGGER_DOWNLOAD_BASE"
            ;;
        linux)
            printf '%s&type=Linux\n' "$PORTSWIGGER_DOWNLOAD_BASE"
            ;;
        *)
            cento_die "Unsupported artifact type '$1'. Use jar or linux."
            ;;
    esac
}

require_downloader() {
    if cento_have_cmd curl; then
        printf 'curl\n'
        return
    fi
    if cento_have_cmd wget; then
        printf 'wget\n'
        return
    fi
    cento_die "Missing required command: curl or wget"
}

download_artifact() {
    local artifact_type=jar
    local output_dir=$DOWNLOAD_DIR
    local force=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                artifact_type=${2:-}
                shift 2
                ;;
            --force)
                force=1
                shift
                ;;
            --output-dir)
                output_dir=${2:-}
                shift 2
                ;;
            -h|--help)
                usage
                return 0
                ;;
            *)
                cento_die "Unknown download option: $1"
                ;;
        esac
    done

    cento_ensure_dir "$output_dir"
    local url downloader before after file
    url=$(download_url_for_type "$artifact_type")
    downloader=$(require_downloader)

    before=$(find "$output_dir" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort || true)
    if [[ "$downloader" == curl ]]; then
        if [[ $force -eq 1 ]]; then
            curl -fL --remote-name --remote-header-name --output-dir "$output_dir" "$url"
        else
            curl -fL --remote-name --remote-header-name --no-clobber --output-dir "$output_dir" "$url"
        fi
    else
        if [[ $force -eq 1 ]]; then
            wget --content-disposition -P "$output_dir" "$url"
        else
            wget --content-disposition --no-clobber -P "$output_dir" "$url"
        fi
    fi
    after=$(find "$output_dir" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort || true)

    file=$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | tail -1 || true)
    if [[ -z "$file" ]]; then
        case "$artifact_type" in
            jar)
                file=$(find "$output_dir" -maxdepth 1 -type f -name 'burpsuite_community*.jar' -printf '%f\n' | sort | tail -1)
                ;;
            linux)
                file=$(find "$output_dir" -maxdepth 1 -type f -name 'burpsuite_community_linux*.sh' -printf '%f\n' | sort | tail -1)
                ;;
        esac
    fi
    [[ -n "$file" ]] || cento_die "Download completed but no $artifact_type artifact was found in $output_dir"

    local path="$output_dir/$file"
    [[ "$artifact_type" == linux ]] && chmod +x "$path"
    printf '%s\n' "$path"
}

latest_local_jar() {
    find "$DOWNLOAD_DIR" "$INSTALL_DIR" -maxdepth 1 -type f -name 'burpsuite_community*.jar' -print 2>/dev/null | sort | tail -1
}

write_launcher() {
    local jar_path=$1
    local bin_dir=$2
    cento_ensure_dir "$bin_dir"
    cat > "$bin_dir/burp-community" <<EOF_LAUNCHER
#!/usr/bin/env bash
exec java \${CENTO_BURP_JAVA_OPTS:-} -jar "$jar_path" "\$@"
EOF_LAUNCHER
    chmod +x "$bin_dir/burp-community"
}

setup_burp() {
    local artifact_type=jar
    local install_dir=$INSTALL_DIR
    local bin_dir=$DEFAULT_BIN_DIR
    local force=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                artifact_type=${2:-}
                shift 2
                ;;
            --install-dir)
                install_dir=${2:-}
                shift 2
                ;;
            --bin-dir)
                bin_dir=${2:-}
                shift 2
                ;;
            --force)
                force=1
                shift
                ;;
            -h|--help)
                usage
                return 0
                ;;
            *)
                cento_die "Unknown setup option: $1"
                ;;
        esac
    done

    [[ "$artifact_type" == jar ]] || cento_die "setup currently supports --type jar. Use download --type linux for the installer."
    cento_require_cmd java
    cento_ensure_dir "$install_dir"
    local downloaded jar_path
    jar_path="$install_dir/burpsuite_community.jar"
    if [[ -e "$jar_path" && $force -ne 1 ]]; then
        cento_die "Setup already exists at $jar_path. Use --force to replace it."
    fi
    local -a download_args=(--type jar)
    [[ $force -eq 1 ]] && download_args+=(--force)
    downloaded=$(download_artifact "${download_args[@]}")
    cp "$downloaded" "$jar_path"
    write_launcher "$jar_path" "$bin_dir"
    cento_ensure_dir "$DEFAULT_HOME"
    cat > "$META_FILE" <<EOF_META
BURP_JAR=$jar_path
BURP_LAUNCHER=$bin_dir/burp-community
BURP_SOURCE=$downloaded
EOF_META
    printf 'Installed %s launcher: %s\n' "$APP_NAME" "$bin_dir/burp-community"
    printf 'Active JAR: %s\n' "$jar_path"
}

load_installed_jar() {
    local jar_path=""
    if [[ -f "$META_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$META_FILE"
        jar_path=${BURP_JAR:-}
    fi
    if [[ -z "$jar_path" || ! -f "$jar_path" ]]; then
        jar_path=$(latest_local_jar || true)
    fi
    [[ -n "$jar_path" && -f "$jar_path" ]] || cento_die "No Burp JAR found. Run: cento burp setup"
    printf '%s\n' "$jar_path"
}

is_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid=$(cat "$PID_FILE")
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" >/dev/null 2>&1
}

build_burp_args() {
    local project_file="" config_file="" use_defaults=0 java_opts=""
    local -a passthrough=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --project-file)
                project_file=${2:-}
                shift 2
                ;;
            --config-file)
                config_file=${2:-}
                shift 2
                ;;
            --use-defaults)
                use_defaults=1
                shift
                ;;
            --java-opts)
                java_opts=${2:-}
                shift 2
                ;;
            --)
                shift
                passthrough+=("$@")
                break
                ;;
            *)
                passthrough+=("$1")
                shift
                ;;
        esac
    done

    BURP_JAVA_OPTS=$java_opts
    BURP_ARGS=()
    [[ $use_defaults -eq 1 ]] && BURP_ARGS+=(--use-defaults)
    [[ -n "$project_file" ]] && BURP_ARGS+=(--project-file="$project_file")
    [[ -n "$config_file" ]] && BURP_ARGS+=(--config-file="$config_file")
    BURP_ARGS+=("${passthrough[@]}")
}

controller_start() {
    if is_running; then
        printf '%s already running with PID %s\n' "$APP_NAME" "$(cat "$PID_FILE")"
        return 0
    fi
    cento_require_cmd java
    local jar_path
    jar_path=$(load_installed_jar)
    build_burp_args "$@"
    cento_ensure_dir "$DEFAULT_HOME"
    # shellcheck disable=SC2086
    nohup java $BURP_JAVA_OPTS -jar "$jar_path" "${BURP_ARGS[@]}" >> "$LOG_FILE" 2>&1 &
    printf '%s\n' "$!" > "$PID_FILE"
    printf 'Started %s with PID %s\n' "$APP_NAME" "$(cat "$PID_FILE")"
    printf 'Log: %s\n' "$LOG_FILE"
}

controller_run() {
    cento_require_cmd java
    local jar_path
    jar_path=$(load_installed_jar)
    build_burp_args "$@"
    # shellcheck disable=SC2086
    exec java $BURP_JAVA_OPTS -jar "$jar_path" "${BURP_ARGS[@]}"
}

controller_stop() {
    if ! is_running; then
        rm -f "$PID_FILE"
        printf '%s is not running\n' "$APP_NAME"
        return 0
    fi
    local pid
    pid=$(cat "$PID_FILE")
    kill "$pid"
    rm -f "$PID_FILE"
    printf 'Stopped %s PID %s\n' "$APP_NAME" "$pid"
}

status() {
    printf '%s\n' "$APP_NAME"
    printf 'home: %s\n' "$DEFAULT_HOME"
    if [[ -f "$META_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$META_FILE"
        printf 'jar: %s\n' "${BURP_JAR:-unknown}"
        printf 'launcher: %s\n' "${BURP_LAUNCHER:-unknown}"
        printf 'source: %s\n' "${BURP_SOURCE:-unknown}"
    else
        printf 'setup: not configured\n'
    fi
    if is_running; then
        printf 'process: running pid %s\n' "$(cat "$PID_FILE")"
    else
        printf 'process: stopped\n'
    fi
}

logs() {
    if [[ ${1:-} == "--follow" || ${1:-} == "-f" ]]; then
        touch "$LOG_FILE"
        exec tail -f "$LOG_FILE"
    fi
    [[ -f "$LOG_FILE" ]] || cento_die "No log file yet: $LOG_FILE"
    cat "$LOG_FILE"
}

paths() {
    printf 'home=%s\n' "$DEFAULT_HOME"
    printf 'downloads=%s\n' "$DOWNLOAD_DIR"
    printf 'install=%s\n' "$INSTALL_DIR"
    printf 'metadata=%s\n' "$META_FILE"
    printf 'pid=%s\n' "$PID_FILE"
    printf 'log=%s\n' "$LOG_FILE"
    printf 'launcher=%s\n' "$DEFAULT_BIN_DIR/burp-community"
}

controller() {
    local action=${1:-status}
    [[ $# -gt 0 ]] && shift
    case "$action" in
        start)
            controller_start "$@"
            ;;
        run)
            controller_run "$@"
            ;;
        stop)
            controller_stop
            ;;
        restart)
            controller_stop
            controller_start "$@"
            ;;
        status)
            status
            ;;
        logs)
            logs "$@"
            ;;
        paths)
            paths
            ;;
        *)
            cento_die "Unknown controller action: $action"
            ;;
    esac
}

main() {
    local command=${1:-help}
    [[ $# -gt 0 ]] && shift
    case "$command" in
        help|-h|--help)
            usage
            ;;
        download)
            download_artifact "$@"
            ;;
        setup)
            setup_burp "$@"
            ;;
        controller)
            controller "$@"
            ;;
        start)
            controller_start "$@"
            ;;
        run)
            controller_run "$@"
            ;;
        stop)
            controller_stop
            ;;
        restart)
            controller restart "$@"
            ;;
        status)
            status
            ;;
        logs)
            logs "$@"
            ;;
        paths)
            paths
            ;;
        docs)
            docs
            ;;
        *)
            cento_die "Unknown burp command: $command"
            ;;
    esac
}

main "$@"
