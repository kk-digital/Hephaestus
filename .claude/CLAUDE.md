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

## Project Structure

```
Hephaestus/
├── src/              # Source code
│   ├── core/        # Core functionality
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

## Important Notes

- Always update todo.txt before ending session
- Run tests before refactoring
- Never commit secrets (.env file)
- Use Python 3.13 compatible packages
- Keep requirements.txt complete and up-to-date
