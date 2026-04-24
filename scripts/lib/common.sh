#!/usr/bin/env bash

if [[ -n "${CENTO_COMMON_SH_LOADED:-}" ]]; then
    return 0
fi
readonly CENTO_COMMON_SH_LOADED=1

cento_timestamp() {
    date +"%Y%m%d-%H%M%S"
}

cento_log() {
    local level=$1
    shift
    printf '[%s] %s\n' "$level" "$*" >&2
}

cento_info() {
    cento_log INFO "$@"
}

cento_warn() {
    cento_log WARN "$@"
}

cento_die() {
    cento_log ERROR "$@"
    exit 1
}

cento_have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

cento_require_cmd() {
    local cmd=$1
    cento_have_cmd "$cmd" || cento_die "Missing required command: $cmd"
}

cento_repo_root() {
    local script_dir
    script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
    printf '%s\n' "$script_dir"
}

cento_ensure_dir() {
    mkdir -p "$1"
}

cento_abs_path() {
    local path=$1
    if [[ -d "$path" ]]; then
        (cd -- "$path" && pwd)
    else
        local dir
        dir=$(cd -- "$(dirname -- "$path")" && pwd)
        printf '%s/%s\n' "$dir" "$(basename -- "$path")"
    fi
}
