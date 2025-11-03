#!/bin/bash
# Hephaestus Service Startup Script
# This script starts all Hephaestus services in tmux sessions

set -e

echo "==================================="
echo "HEPHAESTUS SERVICE STARTUP"
echo "==================================="
echo ""

# Check if we're running inside the container
if [ ! -d "/home/user/workspace/Hephaestus" ]; then
    echo "ERROR: This script must be run inside the Docker container"
    echo "Usage: ssh user@localhost -p 2224 'bash /home/user/workspace/Hephaestus/startup-services.sh'"
    exit 1
fi

cd /home/user/workspace/Hephaestus

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found!"
    echo "Please create .env file with API keys before starting services."
    echo ""
    echo "Run these commands:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Add your API keys"
    echo ""
    exit 1
fi

# Check if databases are initialized
if [ ! -f "./hephaestus.db" ]; then
    echo "WARNING: SQLite database not initialized!"
    echo "Please initialize database before starting services."
    echo ""
    echo "Run this command:"
    echo "  source .venv/bin/activate && python scripts/init_db.py"
    echo ""
    exit 1
fi

echo "Checking existing tmux sessions..."
EXISTING_SESSIONS=$(tmux ls 2>/dev/null | grep -E "^(mcp|monitor|frontend):" || true)
if [ -n "$EXISTING_SESSIONS" ]; then
    echo "WARNING: Some Hephaestus sessions already exist:"
    echo "$EXISTING_SESSIONS"
    echo ""
    read -p "Kill existing sessions and restart? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing sessions..."
        tmux kill-session -t mcp 2>/dev/null || true
        tmux kill-session -t monitor 2>/dev/null || true
        tmux kill-session -t frontend 2>/dev/null || true
        sleep 2
    else
        echo "Keeping existing sessions. Exiting."
        exit 0
    fi
fi

echo ""
echo "Starting services in tmux sessions..."
echo ""

# Start MCP server
echo "[1/3] Starting MCP server (backend)..."
tmux new-session -d -s mcp \
    'cd /home/user/workspace/Hephaestus && source .venv/bin/activate && python run_server.py'
sleep 1
echo "  ✓ MCP server started (tmux session: mcp)"

# Start monitoring service
echo "[2/3] Starting monitoring service..."
tmux new-session -d -s monitor \
    'cd /home/user/workspace/Hephaestus && source .venv/bin/activate && python run_monitor.py'
sleep 1
echo "  ✓ Monitoring started (tmux session: monitor)"

# Start frontend dev server
echo "[3/3] Starting frontend dev server..."
tmux new-session -d -s frontend \
    'cd /home/user/workspace/Hephaestus/frontend && npm install --silent && npm run dev'
sleep 2
echo "  ✓ Frontend started (tmux session: frontend)"

echo ""
echo "==================================="
echo "SERVICES STARTED SUCCESSFULLY"
echo "==================================="
echo ""

# Wait a moment for services to initialize
echo "Waiting for services to initialize..."
sleep 5

# Check health
echo ""
echo "Checking service health..."
HEALTH_CHECK=$(curl -s http://localhost:8000/health 2>/dev/null || echo "failed")
if [[ "$HEALTH_CHECK" == *"healthy"* ]]; then
    echo "  ✓ MCP server is healthy"
else
    echo "  ✗ MCP server health check failed"
    echo "    Run: tmux attach -t mcp (to view logs)"
fi

echo ""
echo "Active tmux sessions:"
tmux ls | grep -E "^(mcp|monitor|frontend):" || echo "  No sessions found"

echo ""
echo "==================================="
echo "ACCESS INFORMATION"
echo "==================================="
echo ""
echo "From your host machine (macOS):"
echo "  Web UI:      http://localhost:3001"
echo "  MCP API:     http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "  Qdrant:      http://localhost:6334"
echo ""
echo "View logs:"
echo "  MCP server:  tmux attach -t mcp"
echo "  Monitoring:  tmux attach -t monitor"
echo "  Frontend:    tmux attach -t frontend"
echo "  (Detach with: Ctrl+B, then D)"
echo ""
echo "Test health:"
echo "  curl http://localhost:8000/health"
echo ""
echo "Create test task:"
echo "  curl -X POST http://localhost:8000/mcp/create_task \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"description\": \"Test task\"}'"
echo ""
echo "==================================="
