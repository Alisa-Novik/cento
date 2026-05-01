#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
COMPOSE_FILE="$ROOT/compose.yml"
PROJECT_NAME="cento-redmine-career"

usage() {
  cat <<'USAGE'
Usage: redmine-compose-root.sh <compose-command> [args...]

Allowed commands:
  up         Start the Redmine stack
  down       Stop the Redmine stack
  ps         Show service status
  logs       Follow logs
  restart    Restart services
  start      Start stopped services
  stop       Stop running services
  config     Render and validate compose config
USAGE
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

command=${1}
shift || true

case "$command" in
  up|down|ps|logs|restart|start|stop|config)
    if [[ ! -f "$ENV_FILE" ]]; then
      echo "Missing $ENV_FILE. Run ./scripts/redmine.sh init first." >&2
      exit 1
    fi
    exec docker compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$command" "$@"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
