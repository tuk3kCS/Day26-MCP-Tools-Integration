# SQLite & PostgreSQL Database FastMCP Server (Lab Submission)

This repository contains a complete, production-grade Model Context Protocol (MCP) server built with **FastMCP** in Python. The server exposes a relational database schema, tables, and records through a set of secure, parameterized tools and dynamic schema resources.

## Features

### 1. Unified Database Adapter (`db.py`)
- **Shared Interface**: Abstract class `DatabaseAdapter` exposes common database behaviors.
- **Dual Support (Bonus Feature)**: Built-in `SQLiteAdapter` and `PostgreSQLAdapter` classes. If the `DATABASE_URL` environment variable is defined, the server seamlessly switches to PostgreSQL; otherwise, it defaults to SQLite (`sqlite_lab.db`).
- **SQL Parametrization & Safety**: Column and table names are fully validated against the database schema before query assembly to prevent SQL injection. Filter values are passed securely using named bindings (`:param` for SQLite, `%(param)s` for PostgreSQL).
- **Auto-Closing Connections**: Implements a `connection` context manager to guarantee connection closing and prevent file locking issues on Windows.

### 2. Core Tools
- `search`: Relational search query supporting selection of columns, multi-clause filters, ordering, pagination (`limit`/`offset`), and safety capping of 100 rows per query.
- `insert`: Standard insertion tool that validates payload inputs against target schemas, executing a parameterized `INSERT` and returning the inserted payload along with the auto-generated primary key ID.
- `aggregate`: Computes SQL aggregate functions (`COUNT`, `AVG`, `SUM`, `MIN`, `MAX`) with optional filters and `GROUP BY` groupings.

### 3. Dynamic Resources
- `schema://database`: Exposes the entire database schema (tables, column names, and data types) as a JSON snapshot.
- `schema://table/{table_name}`: Dynamic template resource exposing the column schema for a specific table name.

### 4. Dual Transports (Bonus Feature)
- **STDIO Transport**: Default, highly optimized transport for local integration with MCP clients (e.g. Antigravity IDE, Gemini CLI, Claude Code).
- **FastAPI / SSE Transport with API Key Auth**: Running with `--sse` spins up a FastAPI SSE server. The server implements middleware authentication checking headers (`X-API-Key`) or query parameters (`?api_key=...`) against the `MCP_API_KEY` env variable.

---

## Project Structure

```text
implementation/
  ├── db.py               # Unified SQLite & PostgreSQL adapter interface and logic
  ├── init_db.py          # Database schema creator and seed generator
  ├── mcp_server.py       # FastMCP server wrapping tools, resources, and SSE transport
  ├── verify_server.py    # Manual verification runner to inspect output formatting
  └── tests/
      └── test_server.py  # Fully isolated automated test suite (16 tests)
.agents/
  └── mcp_config.json     # Workspace level Antigravity configuration
README.md                 # Project documentation and submission instructions
```

---

## Installation & Setup

### 1. Install Dependencies
Verify Python 3.10+ is installed, then install `fastmcp` and `psycopg2-binary` (required for PostgreSQL adapter):
```bash
pip install fastmcp psycopg2-binary
```

### 2. Initialize and Seed the Database
Run the setup script to initialize the tables (`students`, `courses`, `enrollments`) and populate them with standard seed records:
```bash
python implementation/init_db.py
```
Output:
```text
Initializing SQLite database at: C:\Users\Admin\Documents\GitHub\Day26-Track3-MCP-tool-integration\implementation\sqlite_lab.db
SQLite database successfully initialized and seeded.
```

---

## Running Verification

### 1. Run Automated Test Suite
The test suite consists of 16 tests covering all edge cases, validations, filters, and schema resources. Each test case runs in database-level isolation:
```bash
python -m unittest implementation/tests/test_server.py
```
Output:
```text
Ran 16 tests in 0.573s

OK
```

### 2. Manual Verification Script
Run the manual verification runner to inspect the exact outputs, schemas, and error responses returned by the server:
```bash
python implementation/verify_server.py
```

This script will run and output:
- Full schema discovery
- Dynamic schema template lookup
- Successful searches and inserts
- Average and count aggregations
- Clear, descriptive validation errors for nonexistent tables or unsupported operators.

---

## Client Integration

### 1. Antigravity Configuration (IDE & CLI)
Antigravity discovers and registers local MCP servers using `mcp_config.json`. 

#### Global IDE Config Path:
- `C:\Users\Admin\.gemini\config\mcp_config.json`

#### Global CLI Config Path:
- `C:\Users\Admin\.gemini\antigravity-cli\mcp_config.json`

#### Workspace Level Config Path:
- `C:\Users\Admin\Documents\GitHub\Day26-Track3-MCP-tool-integration\.agents\mcp_config.json`

Configure the server with the following settings (which have been pre-written during setup):
```json
{
  "mcpServers": {
    "sqlite-lab": {
      "command": "C:\\Python314\\python.exe",
      "args": [
        "C:\\Users\\Admin\\Documents\\GitHub\\Day26-Track3-MCP-tool-integration\\implementation\\mcp_server.py"
      ],
      "cwd": "C:\\Users\\Admin\\Documents\\GitHub\\Day26-Track3-MCP-tool-integration\\implementation"
    }
  }
}
```

### 2. MCP Inspector
To test tool discovery, schemas, and live executions through the MCP Inspector UI:
```bash
npx -y @modelcontextprotocol/inspector C:\Python314\python.exe C:\Users\Admin\Documents\GitHub\Day26-Track3-MCP-tool-integration\implementation\mcp_server.py
```

### 3. SSE Transport with Authentication (Bonus Mode)
To run the server in remote SSE transport mode:
```bash
# Set custom API key and transport mode
set MCP_TRANSPORT=sse
set MCP_API_KEY=my-secure-key
python implementation/mcp_server.py
```
The server starts on `http://127.0.0.1:8000/mcp`. Any connection request (e.g. `/mcp/sse`) must pass headers `X-API-Key: my-secure-key` or query parameter `?api_key=my-secure-key` to authorize.