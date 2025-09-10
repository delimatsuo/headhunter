#!/bin/bash

# Webhook Server Startup Script
# Starts the local webhook server for Headhunter AI processing

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WEBHOOK_SERVER="$SCRIPT_DIR/webhook_server.py"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements_webhook.txt"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$LOG_DIR/webhook_server.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
ENVIRONMENT="${ENVIRONMENT:-development}"
HOST="${WEBHOOK_HOST:-localhost}"
PORT="${WEBHOOK_PORT:-8080}"
WORKERS="${WEBHOOK_WORKERS:-3}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if server is running
is_server_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            # Stale PID file
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check Ollama
    if ! command -v ollama &> /dev/null; then
        log_warn "Ollama not found in PATH. Install with: brew install ollama"
    else
        log_info "✓ Ollama found"
        
        # Check if Ollama service is running
        if ! curl -s http://localhost:11434/api/version > /dev/null; then
            log_warn "Ollama service not running. Starting it..."
            ollama serve &
            sleep 3
        fi
        
        # Check if model is available
        if ! ollama list | grep -q "llama3.1:8b"; then
            log_warn "Model llama3.1:8b not found. Pulling it..."
            ollama pull llama3.1:8b
        fi
    fi
    
    # Create directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$PROJECT_ROOT/webhook_results"
    mkdir -p "$PROJECT_ROOT/temp_resumes"
}

# Install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."
    
    if [ -f "$REQUIREMENTS_FILE" ]; then
        pip3 install -r "$REQUIREMENTS_FILE" > /dev/null 2>&1
        log_success "Dependencies installed"
    else
        log_warn "Requirements file not found: $REQUIREMENTS_FILE"
    fi
}

# Start server
start_server() {
    if is_server_running; then
        log_warn "Webhook server is already running (PID: $(cat "$PID_FILE"))"
        return 0
    fi
    
    log_info "Starting webhook server..."
    log_info "  Environment: $ENVIRONMENT"
    log_info "  Host: $HOST"
    log_info "  Port: $PORT"
    log_info "  Log file: $LOG_DIR/webhook_server.log"
    
    # Export environment variables
    export ENVIRONMENT="$ENVIRONMENT"
    export WEBHOOK_HOST="$HOST"
    export WEBHOOK_PORT="$PORT"
    
    # Start server in background
    cd "$SCRIPT_DIR"
    python3 "$WEBHOOK_SERVER" \
        --env "$ENVIRONMENT" \
        --host "$HOST" \
        --port "$PORT" \
        > "$LOG_DIR/webhook_server.log" 2>&1 &
    
    local server_pid=$!
    echo $server_pid > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 3
    if ps -p $server_pid > /dev/null 2>&1; then
        log_success "Webhook server started successfully (PID: $server_pid)"
        log_info "  Server URL: http://$HOST:$PORT"
        log_info "  Health check: http://$HOST:$PORT/health"
        log_info "  Metrics: http://$HOST:$PORT/metrics"
        return 0
    else
        log_error "Failed to start webhook server"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Stop server
stop_server() {
    if ! is_server_running; then
        log_warn "Webhook server is not running"
        return 0
    fi
    
    local pid=$(cat "$PID_FILE")
    log_info "Stopping webhook server (PID: $pid)..."
    
    kill "$pid" 2>/dev/null || true
    
    # Wait for graceful shutdown
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        ((count++))
    done
    
    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        log_warn "Forcing server shutdown..."
        kill -9 "$pid" 2>/dev/null || true
    fi
    
    rm -f "$PID_FILE"
    log_success "Webhook server stopped"
}

# Show status
show_status() {
    if is_server_running; then
        local pid=$(cat "$PID_FILE")
        log_success "Webhook server is running (PID: $pid)"
        
        # Try to get server status
        if command -v curl &> /dev/null; then
            log_info "Checking server health..."
            if curl -s "http://$HOST:$PORT/health" > /dev/null; then
                log_success "Server is healthy and responding"
            else
                log_warn "Server is running but not responding to health checks"
            fi
        fi
    else
        log_warn "Webhook server is not running"
        return 1
    fi
}

# Run tests
run_tests() {
    log_info "Running webhook integration tests..."
    
    if [ ! -f "$SCRIPT_DIR/webhook_test.py" ]; then
        log_error "Test file not found: $SCRIPT_DIR/webhook_test.py"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python3 webhook_test.py --host "$HOST" --port "$PORT"
}

# Show logs
show_logs() {
    local log_file="$LOG_DIR/webhook_server.log"
    if [ -f "$log_file" ]; then
        tail -f "$log_file"
    else
        log_error "Log file not found: $log_file"
        return 1
    fi
}

# Main command handling
case "${1:-start}" in
    "start")
        check_prerequisites
        install_dependencies
        start_server
        ;;
    "stop")
        stop_server
        ;;
    "restart")
        stop_server
        sleep 2
        check_prerequisites
        start_server
        ;;
    "status")
        show_status
        ;;
    "test")
        run_tests
        ;;
    "logs")
        show_logs
        ;;
    "install")
        check_prerequisites
        install_dependencies
        log_success "Installation completed"
        ;;
    "help"|"-h"|"--help")
        echo "Webhook Server Management Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  start     Start the webhook server (default)"
        echo "  stop      Stop the webhook server"
        echo "  restart   Restart the webhook server"
        echo "  status    Check server status"
        echo "  test      Run integration tests"
        echo "  logs      Show server logs (tail -f)"
        echo "  install   Install dependencies only"
        echo "  help      Show this help message"
        echo ""
        echo "Environment Variables:"
        echo "  ENVIRONMENT     Server environment (development, production, testing)"
        echo "  WEBHOOK_HOST    Server host (default: localhost)"
        echo "  WEBHOOK_PORT    Server port (default: 8080)"
        echo ""
        echo "Examples:"
        echo "  $0 start                    # Start with defaults"
        echo "  WEBHOOK_PORT=9000 $0 start  # Start on port 9000"
        echo "  ENVIRONMENT=production $0 start"
        echo ""
        ;;
    *)
        log_error "Unknown command: $1"
        log_info "Run '$0 help' for usage information"
        exit 1
        ;;
esac