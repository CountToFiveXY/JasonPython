#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$project_dir/.venv/bin/python"
redis_started=0
temporal_pid=""
worker_pid=""
api_pid=""

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

wait_for_port() {
    local host="$1"
    local port="$2"
    local service="$3"

    for _ in {1..30}; do
        if nc -z "$host" "$port" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    echo "$service did not become ready at $host:$port" >&2
    return 1
}

cleanup() {
    trap - EXIT INT TERM

    for pid in "$api_pid" "$worker_pid" "$temporal_pid"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done

    if [[ "$redis_started" -eq 1 ]]; then
        redis-cli shutdown >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT INT TERM

require_command redis-server
require_command redis-cli
require_command temporal
require_command nc

if [[ ! -x "$python_bin" ]]; then
    echo "Python virtual environment not found at $project_dir/.venv" >&2
    echo "Create it and install dependencies before running this script." >&2
    exit 1
fi

cd "$project_dir"

if redis-cli ping >/dev/null 2>&1; then
    echo "Redis is already running."
else
    echo "Starting Redis..."
    redis-server --daemonize yes
    redis_started=1
    wait_for_port 127.0.0.1 6379 Redis
fi

if nc -z 127.0.0.1 7233 >/dev/null 2>&1; then
    echo "Temporal Server is already running."
else
    echo "Starting Temporal Server..."
    temporal server start-dev &
    temporal_pid=$!
    wait_for_port 127.0.0.1 7233 "Temporal Server"
fi

echo "Starting Temporal worker..."
"$python_bin" -m temporal_service.worker &
worker_pid=$!

echo "Starting FastAPI at http://127.0.0.1:8080..."
"$python_bin" -m uvicorn main:app --reload --host 0.0.0.0 --port 8080 &
api_pid=$!

echo "Temporal Web UI: http://127.0.0.1:8233"
echo "Press Control+C to stop the processes started by this script."
wait "$api_pid"
