#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_dir="$project_dir/.venv"
python_bin="$venv_dir/bin/python"
requirements_file="$project_dir/requirements.txt"
requirements_stamp="$venv_dir/.requirements.sha256"
api_port_file="$venv_dir/jasonapp-api-port"
services_pid_file="$venv_dir/jasonapp-services.pid"
redis_data_dir="${REDIS_DATA_DIR:-$(dirname "$project_dir")/redis}"
firebase_credentials_default="$HOME/.config/jasonapp/service-account.json"
kafka_bootstrap_servers="${KAFKA_BOOTSTRAP_SERVERS:-127.0.0.1:9092}"
kafka_topic="${KAFKA_TOPIC:-backend-messages}"
redis_started=0
kafka_started=0
temporal_pid=""
worker_pid=""
kafka_worker_pid=""
api_pid=""
api_port=""

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]] && \
   [[ -f "$firebase_credentials_default" ]]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$firebase_credentials_default"
fi

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

install_system_dependencies() {
    local formulas=()

    if ! command -v brew >/dev/null 2>&1; then
        highlight_error "Homebrew is required to install Redis, Kafka, Temporal, and Python dependencies."
        highlight_error "Install Homebrew from https://brew.sh, then run this script again."
        exit 1
    fi
    command -v redis-server >/dev/null 2>&1 || formulas+=(redis)
    command -v temporal >/dev/null 2>&1 || formulas+=(temporal)
    if [[ "$kafka_bootstrap_servers" == "127.0.0.1:9092" ]] && \
       ! command -v kafka-server-start >/dev/null 2>&1; then
        formulas+=(kafka)
    fi
    command -v python3 >/dev/null 2>&1 || formulas+=(python)

    if (( ${#formulas[@]} > 0 )); then
        highlight "Installing missing system dependencies: ${formulas[*]}"
        if ! brew install "${formulas[@]}"; then
            highlight_error "Could not install the required Homebrew packages."
            highlight_error "Open Terminal and run: brew update"
            highlight_error "Then run: brew install ${formulas[*]}"
            highlight_error "After installation finishes, click Activate All Services again."
            exit 1
        fi
    fi
}

prepare_python_environment() {
    local current_hash
    local installed_hash=""

    if [[ ! -x "$python_bin" ]]; then
        highlight "Creating Python virtual environment at $venv_dir..."
        if ! python3 -m venv "$venv_dir"; then
            highlight_error "Could not create the Python virtual environment."
            highlight_error "Open Terminal and run: brew install python"
            highlight_error "Then click Activate All Services again."
            exit 1
        fi
    fi

    current_hash="$(shasum -a 256 "$requirements_file" | awk '{print $1}')"
    if [[ -f "$requirements_stamp" ]]; then
        installed_hash="$(<"$requirements_stamp")"
    fi

    if [[ "$current_hash" != "$installed_hash" ]]; then
        highlight "Installing Python dependencies..."
        if ! "$python_bin" -m pip install --upgrade pip || \
           ! "$python_bin" -m pip install -r "$requirements_file"; then
            highlight_error "Could not install the Python dependencies."
            highlight_error "Check your internet connection, then click Activate All Services again."
            highlight_error "For manual troubleshooting, run:"
            highlight_error "  $python_bin -m pip install -r $requirements_file"
            exit 1
        fi
        printf '%s\n' "$current_hash" > "$requirements_stamp"
    else
        highlight "Python dependencies are up to date."
    fi
}

select_api_port() {
    local preferred_port="${FASTAPI_PORT:-8000}"
    local candidates=("$preferred_port" 8000 8088 8888)
    local candidate
    local seen=" "

    for candidate in "${candidates[@]}"; do
        if [[ ! "$candidate" =~ ^[0-9]+$ ]] || (( candidate < 1 || candidate > 65535 )); then
            highlight_error "Ignoring invalid FastAPI port: $candidate"
            continue
        fi
        if [[ "$seen" == *" $candidate "* ]]; then
            continue
        fi
        seen+="$candidate "
        if ! nc -z 127.0.0.1 "$candidate" >/dev/null 2>&1; then
            api_port="$candidate"
            printf '%s\n' "$api_port" > "$api_port_file"
            if [[ "$api_port" != "$preferred_port" ]]; then
                highlight "FastAPI port $preferred_port is busy; using $api_port instead."
            fi
            return
        fi
    done

    highlight_error "No FastAPI port is available. Tried: $preferred_port, 8000, 8088, 8888"
    exit 1
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

    for pid in "$api_pid" "$kafka_worker_pid" "$worker_pid" "$temporal_pid"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done

    if [[ "$redis_started" -eq 1 ]]; then
        redis-cli shutdown >/dev/null 2>&1 || true
    fi

    if [[ "$kafka_started" -eq 1 ]]; then
        brew services stop kafka >/dev/null 2>&1 || true
    fi

    rm -f "$api_port_file"
    if [[ -f "$services_pid_file" ]] && [[ "$(<"$services_pid_file")" == "$$" ]]; then
        rm -f "$services_pid_file"
    fi
}

trap cleanup EXIT INT TERM

if [[ -f "$services_pid_file" ]]; then
    previous_pid="$(<"$services_pid_file")"
    if [[ "$previous_pid" =~ ^[0-9]+$ ]] && [[ "$previous_pid" != "$$" ]] && \
       kill -0 "$previous_pid" >/dev/null 2>&1; then
        highlight "Stopping the previous JasonApp service session..."
        kill -TERM "$previous_pid"
        for _ in {1..50}; do
            kill -0 "$previous_pid" >/dev/null 2>&1 || break
            sleep 0.1
        done
        if kill -0 "$previous_pid" >/dev/null 2>&1; then
            highlight_error "The previous JasonApp service session could not be stopped."
            highlight_error "Restart this Mac, then click Activate All Services again."
            exit 1
        fi
    fi
fi
printf '%s\n' "$$" > "$services_pid_file"

rm -f "$api_port_file"
install_system_dependencies
require_command redis-server
require_command redis-cli
require_command temporal
require_command nc
require_command shasum
prepare_python_environment
select_api_port

if [[ ! -d "$redis_data_dir" ]] && ! mkdir -p "$redis_data_dir"; then
    highlight_error "Could not create Redis data directory: $redis_data_dir"
    exit 1
fi

if [[ ! -w "$redis_data_dir" ]]; then
    highlight_error "Redis data directory must exist and be writable: $redis_data_dir"
    exit 1
fi

cd "$project_dir"

if redis-cli ping >/dev/null 2>&1; then
    current_redis_dir="$(redis-cli --raw CONFIG GET dir | tail -n 1)"
    if [[ "$current_redis_dir" != "$redis_data_dir" ]]; then
        highlight_error "Redis is already using a different data directory: $current_redis_dir"
        highlight_error "Stop Redis, then run this script again to use: $redis_data_dir"
        exit 1
    fi
    highlight "Redis is already running."
else
    highlight "Starting Redis..."
    redis-server --daemonize yes --dir "$redis_data_dir" --dbfilename dump.rdb
    redis_started=1
    wait_for_port 127.0.0.1 6379 Redis
fi

highlight "Redis snapshot: $redis_data_dir/dump.rdb"

if [[ "$kafka_bootstrap_servers" == "127.0.0.1:9092" ]]; then
    require_command kafka-topics
    if nc -z 127.0.0.1 9092 >/dev/null 2>&1; then
        highlight "Kafka is already running."
    else
        highlight "Starting Kafka..."
        brew services start kafka
        kafka_started=1
        wait_for_port 127.0.0.1 9092 Kafka
    fi
    kafka-topics \
        --bootstrap-server "$kafka_bootstrap_servers" \
        --create \
        --if-not-exists \
        --topic "$kafka_topic"
else
    highlight "Using external Kafka broker: $kafka_bootstrap_servers"
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
"$python_bin" -m src.temporal.worker &
worker_pid=$!

highlight "Starting Kafka message worker..."
"$python_bin" -m src.messaging.worker &
kafka_worker_pid=$!

highlight "Starting FastAPI at http://127.0.0.1:$api_port..."
"$python_bin" -m uvicorn src.main:app --host 0.0.0.0 --port "$api_port" &
api_pid=$!

highlight_link "Temporal Web UI" "http://127.0.0.1:8233"
highlight_link "You can now try calling APIs in -->" "http://127.0.0.1:$api_port/docs"
highlight "Press Control+C to stop the processes started by this script."
wait "$api_pid"
