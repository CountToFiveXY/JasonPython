#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$project_dir/.venv/bin/python"
redis_started=0
temporal_pid=""
worker_pid=""
api_pid=""

if [[ -t 1 ]]; then
    highlight_color=$'\033[1;38;5;208m'
    highlight_reset=$'\033[0m'
else
    highlight_color=""
    highlight_reset=""
fi

if [[ -t 2 ]]; then
    error_color=$'\033[1;31m'
    error_reset=$'\033[0m'
else
    error_color=""
    error_reset=""
fi

highlight() {
    printf '%s%s%s\n' "$highlight_color" "$*" "$highlight_reset"
}

highlight_error() {
    printf '%s%s%s\n' "$error_color" "$*" "$error_reset" >&2
}

highlight_link() {
    local label="$1"
    local url="$2"

    if [[ -t 1 ]]; then
        printf '%s%s: \033]8;;%s\033\\%s\033]8;;\033\\%s\n' \
            "$highlight_color" "$label" "$url" "$url" "$highlight_reset"
    else
        printf '%s: %s\n' "$label" "$url"
    fi
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        highlight_error "Required command not found: $1"
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

    highlight_error "$service did not become ready at $host:$port"
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
    highlight_error "Python virtual environment not found at $project_dir/.venv"
    highlight_error "Create it and install dependencies before running this script."
    exit 1
fi

cd "$project_dir"

if redis-cli ping >/dev/null 2>&1; then
    highlight "Redis is already running."
else
    highlight "Starting Redis..."
    redis-server --daemonize yes
    redis_started=1
    wait_for_port 127.0.0.1 6379 Redis
fi

if nc -z 127.0.0.1 7233 >/dev/null 2>&1; then
    highlight "Temporal Server is already running."
else
    highlight "Starting Temporal Server..."
    temporal server start-dev &
    temporal_pid=$!
    wait_for_port 127.0.0.1 7233 "Temporal Server"
fi

highlight "Starting Temporal worker..."
"$python_bin" -m temporal.worker &
worker_pid=$!

highlight "Starting FastAPI at http://127.0.0.1:8080..."
"$python_bin" -m uvicorn main:app --reload --host 0.0.0.0 --port 8080 &
api_pid=$!

highlight_link "Temporal Web UI" "http://127.0.0.1:8233"
highlight_link "You can now try calling APIs in -->" "http://127.0.0.1:8080/docs"
highlight "Press Control+C to stop the processes started by this script."
wait "$api_pid"
