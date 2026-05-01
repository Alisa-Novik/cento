#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
COMPOSE_FILE="$ROOT/compose.yml"
PROJECT_NAME="cento-redmine-career"
SUDO_COMPOSE_HELPER="$ROOT/scripts/redmine-compose-root.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/redmine.sh <command>

Commands:
  init       Create .env with generated local secrets when missing
  up         Start Redmine and PostgreSQL
  cutover-stop  Stop Redmine stack for validation window (requires sudo helper)
  cutover-start Start Redmine stack after a cutover window (requires sudo helper)
  cutover-status Show compose status for validation window checks (requires sudo helper)
  down       Stop the stack
  restart    Restart the stack
  logs       Follow Redmine logs
  ps         Show stack containers
  seed-sample Create/update the career-consulting sample project
  url        Print the local Redmine URL
  doctor     Check local runtime prerequisites

Default login after first boot:
  admin / admin
USAGE
}

runtime() {
  if command -v docker >/dev/null 2>&1; then
    echo docker
    return 0
  fi
  if command -v podman >/dev/null 2>&1; then
    echo podman
    return 0
  fi
  return 1
}

require_runtime() {
  if ! runtime >/dev/null; then
    echo "No Docker-compatible runtime found. Install Docker Engine or Podman first." >&2
    exit 1
  fi
}

compose() {
  local rt
  require_runtime
  rt="$(runtime)"
  if [[ "$rt" == docker ]]; then
    docker compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
  else
    podman compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
  fi
}

compose_as_root() {
  local action=${1:-}
  shift || true
  if [[ ! -x "$SUDO_COMPOSE_HELPER" ]]; then
    echo "Missing privileged helper: $SUDO_COMPOSE_HELPER" >&2
    echo "Create the least-privilege sudoers entry documented in docs/redmine-retirement-roadmap.md" >&2
    exit 1
  fi
  local output
  if ! output="$(sudo -n "$SUDO_COMPOSE_HELPER" "$action" "$@" 2>&1)"; then
    echo "$output" >&2
    echo "If this is a permission issue, add a restricted sudoers entry for $SUDO_COMPOSE_HELPER." >&2
    echo "See docs/redmine-retirement-roadmap.md under 'Cutover gate command set'." >&2
    return 1
  fi
  if [[ -n "$output" ]]; then
    printf '%s\n' "$output"
  fi
}

random_secret() {
  openssl rand -hex 48
}

ensure_env() {
  if [[ -f "$ENV_FILE" ]]; then
    return 0
  fi

  cp "$ROOT/.env.example" "$ENV_FILE"
  sed -i \
    -e "s/change-me-redmine-db-password/$(random_secret)/" \
    -e "s/change-me-postgres-root-password/$(random_secret)/" \
    -e "s/change-me-long-random-secret/$(random_secret)/" \
    "$ENV_FILE"
}

port() {
  if [[ -f "$ENV_FILE" ]]; then
    awk -F= '$1 == "REDMINE_PORT" { print $2 }' "$ENV_FILE"
  else
    awk -F= '$1 == "REDMINE_PORT" { print $2 }' "$ROOT/.env.example"
  fi
}

cmd="${1:-}"
case "$cmd" in
  init)
    ensure_env
    echo "Initialized $ENV_FILE"
    ;;
  up)
    ensure_env
    compose up -d
    "$0" url
    ;;
  cutover-stop)
    ensure_env
    compose_as_root down --remove-orphans
    ;;
  cutover-start)
    ensure_env
    compose_as_root up -d
    ;;
  cutover-status)
    ensure_env
    compose_as_root ps
    ;;
  down)
    ensure_env
    compose down
    ;;
  restart)
    ensure_env
    compose restart
    ;;
  logs)
    ensure_env
    compose logs -f redmine
    ;;
  ps)
    ensure_env
    compose ps
    ;;
  seed-sample)
    ensure_env
    compose up -d
    if [[ "$(runtime)" == docker ]]; then
      docker cp "$ROOT/scripts/seed-career-consulting-sample.rb" cento-redmine:/tmp/seed-career-consulting-sample.rb
      docker exec cento-redmine bash -lc 'SECRET_KEY_BASE="$REDMINE_SECRET_KEY_BASE" bundle exec rails runner /tmp/seed-career-consulting-sample.rb'
    else
      podman cp "$ROOT/scripts/seed-career-consulting-sample.rb" cento-redmine:/tmp/seed-career-consulting-sample.rb
      podman exec cento-redmine bash -lc 'SECRET_KEY_BASE="$REDMINE_SECRET_KEY_BASE" bundle exec rails runner /tmp/seed-career-consulting-sample.rb'
    fi
    ;;
  url)
    echo "http://localhost:$(port)"
    ;;
  doctor)
    require_runtime
    ensure_env
    compose config >/dev/null
    echo "Redmine stack prerequisites look OK."
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
