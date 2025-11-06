# Hephaestus Project Guidelines

## Todo List Management

**CRITICAL: Always maintain an up-to-date todo.txt file in the repository root**

- Location: `/home/user/workspace/Hephaestus/Hephaestus/todo.txt` (in container)
- Host location: `~/claude/claude-docker.hephaestus/Hephaestus/Hephaestus/todo.txt`
- Keep todo.txt committed to git for session handoffs
- Update status as work progresses
- Mark completed items with [DONE]
- Add new todos when starting work

## Development Environment

**Container Development:**
- SSH: `ssh user@localhost -p 2224`
- Working directory: `/home/user/workspace/Hephaestus/Hephaestus/`
- Branch: `dev-haltingstate-00`
- Python: 3.13 (requires SQLAlchemy >= 2.0.35 for compatibility)

**Virtual Environment:**
```bash
source .venv/bin/activate  # Inside container
```

## Testing

**Run tests:**
```bash
pytest tests/          # All tests
pytest tests/ -v       # Verbose
pytest tests/ -k test_name  # Specific test
```

**Test Dependencies:**
All test dependencies are in `requirements.txt`:
- pytest, pytest-asyncio
- gitpython, python-jose
- passlib, bcrypt, email-validator

**Test Status:**
- 449 tests collected successfully
- 1 expected error: `tests/manual_validation_test.py` (requires running server)

## API Keys Configuration

**Required keys for tests:**
- OpenAI API key
- OpenRouter API key

**Configuration location:**
```bash
# Set in .env file (not committed)
OPENAI_API_KEY=your-key-here
OPENROUTER_API_KEY=your-key-here
```

**IMPORTANT:** Never commit API keys to git. Use .env file (already in .gitignore).

## Dependencies

**Python 3.13 Compatibility:**
- SQLAlchemy must be >= 2.0.35 (2.0.23 is NOT compatible)
- LangChain 1.0.x series (langchain.schema moved to langchain_core.documents)

**Common Issues:**
- `langchain.schema.Document` -> Use `langchain_core.documents.Document`
- SQLAlchemy AssertionError -> Upgrade to >= 2.0.35

## Git Workflow

**Branch:** `dev-haltingstate-00`

**Commit and push:**
```bash
git add .
git commit -m "description"
git push origin dev-haltingstate-00
git push gogs dev-haltingstate-00  # Backup to Gogs
```

**Remotes:**
- origin: GitHub (kk-digital/Hephaestus)
- gogs: http://localhost:3000/kk-digital/Hephaestus (HTTP auth with API token)

## Architecture Principles

**CRITICAL - Module Consolidation:**

- NO separate enum modules - enums belong in the modules that use them
- NO separate model modules - models belong with their services
- NO separate routes modules - routes belong in the service modules
- NO generic modules (config_loaders, etc) - config classes go in same module as the class using them
- Each service should be ONE module containing: models, enums, service logic, routes

**Database Models:**

- ONE TABLE PER FILE - never define multiple tables in a single file
- Core infrastructure models (Agent, Task, User, etc.) → src/core/database/
- Service-specific models → respective service module (e.g., workflow models in workflow service)
- File naming: lowercase with underscores matching table name (agent_log.py for AgentLog table)

**Module Organization:**

- Each service is ONE module containing all related code
- Example: c2_monitoring_guardian/ contains monitoring models, enums, service logic
- Avoid proliferation of small single-purpose modules

## Project Structure

```
Hephaestus/
├── src/              # Source code
│   ├── core/        # Core functionality & infrastructure models
│   ├── agents/      # Agent implementations
│   ├── interfaces/  # External interfaces
│   └── mcp/         # MCP server
├── tests/           # Test suite
├── config/          # Configuration files
├── tasks/           # Task documentation
└── .env             # API keys (not committed)
```

## Task Files

**Location:** `tasks/` directory

**Format:** `yymmdd-task-NN-description.txt`

**Status suffixes:**
- No suffix: Active
- `.done.txt`: Completed
- `.failed.txt`: Failed/abandoned
- `.pending.txt`: Planned

## Process Management

**CRITICAL: Restart processes after code changes**

After making changes to source code, configuration, or dependencies:

1. **Stop running processes gracefully:**
   ```bash
   # For MCP server (if running)
   curl -X POST http://localhost:8000/shutdown

   # Or send SIGTERM signal
   kill -TERM <pid>
   ```

2. **Wait for graceful shutdown to complete**
   - Server should finish current requests
   - Clean up resources (database connections, file handles)
   - Exit cleanly

3. **Restart with new code:**
   ```bash
   # Inside container
   cd /home/user/workspace/Hephaestus/Hephaestus
   source .venv/bin/activate
   python -m src.mcp.server
   ```

**Graceful Shutdown Requirements:**

All long-running processes MUST implement graceful shutdown:
- **Health endpoint:** `GET /health` - Returns server status
- **Shutdown endpoint:** `POST /shutdown` - Initiates graceful shutdown (blocks until complete)
- **Signal handling:** Respond to SIGTERM/SIGINT signals
- **Cleanup:** Close database connections, flush logs, complete in-flight requests

**Standard health/shutdown endpoints:**
```python
@app.get("/health")
async def health():
    return {"status": "healthy", "uptime": uptime_seconds}

@app.post("/shutdown")
async def shutdown():
    # Block until shutdown completes
    await cleanup_resources()
    await shutdown_server()
    return {"status": "shutdown_complete"}
```

## Important Notes

- Always update todo.txt before ending session
- Run tests before refactoring
- Never commit secrets (.env file)
- Use Python 3.13 compatible packages
- Keep requirements.txt complete and up-to-date
- **ALWAYS restart processes after making code changes**
- **NEVER leave stale processes running with old code**
