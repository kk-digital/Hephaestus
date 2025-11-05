================================================================================
HEPHAESTUS - AI AGENT ORCHESTRATION SYSTEM
================================================================================

Project Name:       Hephaestus
Organization:       kk-digital
Repository:         https://github.com/kk-digital/Hephaestus

GitHub URL (HTTPS): https://github.com/kk-digital/Hephaestus
GitHub URL (SSH):   git@github.com:kk-digital/Hephaestus

================================================================================
PROJECT DESCRIPTION
================================================================================

Hephaestus is an autonomous AI agent orchestration system that manages
multiple AI agents for complex tasks.

Key Features:
- FastAPI server with MCP (Model Context Protocol) for agent communication
- SQLite for relational data, Qdrant for vector storage (RAG)
- tmux sessions for agent isolation
- LLM providers (OpenAI/Anthropic) for task enrichment and monitoring
- Python backend + TypeScript frontend architecture

================================================================================
DOCKER SETUP
================================================================================

This repository has been cloned into a Docker sandbox environment.

Docker Location:    /Users/sp/claude/claude-docker.hephaestus/
Docker Config:      ../docker-hephaestus/
Dockerfile:         ../docker-hephaestus/Dockerfile
Setup Instructions: ../docker-hephaestus/todo.txt

To run in Docker:
1. Navigate to ../docker-hephaestus/
2. Build image: docker build -t hephaestus:latest -f Dockerfile .
3. Run container: See docker-hephaestus/todo.txt for detailed instructions

================================================================================
QUICK START (LOCAL)
================================================================================

Prerequisites:
- Python 3.11+
- Node.js 20.x
- Qdrant (running on port 6333)

Setup:
1. Install Python dependencies:
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Install frontend dependencies:
   cd frontend
   npm install

3. Initialize databases:
   python scripts/init_db.py
   python scripts/init_qdrant.py

4. Configure environment:
   Create .env file with API keys and configuration

5. Start services:
   python run_server.py    # MCP server (port 8000)
   python run_monitor.py   # Monitoring loop
   cd frontend && npm run dev  # Frontend (port 3000)

================================================================================
DOCUMENTATION
================================================================================

Full documentation is available in the repository:
- README.md - Project overview and setup
- CLAUDE.md - Development guidelines for Claude Code
- docs/ - Comprehensive documentation
- design_docs/ - Design specifications

================================================================================
END OF README
================================================================================
