#!/usr/bin/env bash
set -euo pipefail
CMD=${1:-up}
TICK=${TICK:-0}
compose="docker-compose.yml"
override="docker-compose.no-tick.yml"
if [ "$TICK" = "1" ]; then
  override="docker-compose.tick.yml"
fi
case "$CMD" in
  up)    docker compose -f "$compose" -f "$override" up --build ;;
  build) docker compose -f "$compose" -f "$override" build --no-cache ;;
  down)  docker compose -f "$compose" -f "$override" down -v ;;
  *) echo "Usage: TICK=0|1 ./dev.sh [up|build|down]"; exit 1 ;; esac
