import os
import sys
import json
import logging
from typing import Optional, List, Dict, Any

from fastmcp import FastMCP

# Ensure the parent/implementation directory is in path to import db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_adapter, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_db_server")

# Initialize database adapter
adapter = get_adapter()

# Create the FastMCP server
mcp = FastMCP("SQLite Lab MCP Server")

@mcp.tool(name="search")
def search(
    table: str,
    columns: Optional[List[str]] = None,
    filters: Optional[Any] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: Optional[str] = None,
    descending: bool = False
) -> str:
    """
    Search records in the database table with support for filters, ordering, and pagination.

    Args:
        table (str): Table name to query (e.g., 'students', 'courses', 'enrollments').
        columns (list, optional): List of columns to return. Defaults to all.
        filters (dict/list, optional): Dictionary or list of filters. E.g. {"cohort": "A1"} or [{"column": "grade", "operator": ">=", "value": 85.0}].
            Supported operators: =, !=, <, >, <=, >=, LIKE, IN.
        limit (int, optional): Maximum number of rows to return (capped at 100). Default 20.
        offset (int, optional): Number of rows to skip. Default 0.
        order_by (str, optional): Column name to sort by.
        descending (bool, optional): Sort in descending order. Default False.
    """
    try:
        results = adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending
        )
        return json.dumps(results, indent=2, ensure_ascii=False)
    except ValidationError as e:
        return f"Validation Error: {str(e)}"
    except Exception as e:
        return f"Error executing search: {str(e)}"


@mcp.tool(name="insert")
def insert(table: str, values: Dict[str, Any]) -> str:
    """
    Insert a record into the database table and return the inserted payload.

    Args:
        table (str): Table name to insert into.
        values (dict): Column-value mappings of the record to insert. E.g. {"name": "Hieu", "email": "hieu@example.com", "cohort": "A1"}
    """
    try:
        result = adapter.insert(table=table, values=values)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except ValidationError as e:
        return f"Validation Error: {str(e)}"
    except Exception as e:
        return f"Error executing insert: {str(e)}"


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: Optional[str] = None,
    filters: Optional[Any] = None,
    group_by: Optional[List[str]] = None
) -> str:
    """
    Compute aggregate metrics on a database table (e.g. count, average, sum, min, max).

    Args:
        table (str): Table name to query.
        metric (str): Aggregate function. Must be 'count', 'avg', 'sum', 'min', or 'max'.
        column (str, optional): Column to aggregate. Required for avg, sum, min, max.
        filters (dict/list, optional): Optional filters to apply before aggregating.
        group_by (list/str, optional): Column(s) to group by.
    """
    try:
        results = adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by
        )
        return json.dumps(results, indent=2, ensure_ascii=False)
    except ValidationError as e:
        return f"Validation Error: {str(e)}"
    except Exception as e:
        return f"Error executing aggregate: {str(e)}"


@mcp.resource("schema://database")
def database_schema() -> str:
    """
    Get the full database schema definitions (all tables and their columns).
    """
    try:
        tables = adapter.list_tables()
        schema = {}
        for table in tables:
            schema[table] = adapter.get_table_schema(table)
        return json.dumps(schema, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error retrieving schema: {str(e)}"


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """
    Get the schema definition for a specific table.
    """
    try:
        adapter.validate_table(table_name)
        schema = adapter.get_table_schema(table_name)
        return json.dumps({table_name: schema}, indent=2, ensure_ascii=False)
    except ValidationError as e:
        return f"Validation Error: {str(e)}"
    except Exception as e:
        return f"Error retrieving schema for '{table_name}': {str(e)}"


if __name__ == "__main__":
    # Check if we should run SSE server
    if "--sse" in sys.argv or os.environ.get("MCP_TRANSPORT") == "sse":
        import uvicorn
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from mcp.server.fastapi import create_sse_server
        
        port = int(os.environ.get("PORT", "8000"))
        host = os.environ.get("HOST", "127.0.0.1")
        
        app = FastAPI(title="SQLite Lab MCP Server - SSE")
        
        # Authentication middleware for SSE & messages endpoints (bonus points task)
        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            # Intercept any requests targeting our MCP mounts
            if request.url.path.startswith("/mcp"):
                expected_key = os.environ.get("MCP_API_KEY", "secret-key")
                api_key = request.headers.get("X-API-Key")
                if not api_key:
                    api_key = request.query_params.get("api_key")
                
                if api_key != expected_key:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Unauthorized: Invalid or missing X-API-Key"}
                    )
            
            response = await call_next(request)
            return response

        # Mount our FastMCP server via SSE protocol
        app.mount("/mcp", create_sse_server(mcp))
        
        logger.info(f"Starting SSE MCP Server on http://{host}:{port}/mcp")
        logger.info(f"Authentication active. Expecting header 'X-API-Key: <secret-key>' or parameter '?api_key=<secret-key>'")
        uvicorn.run(app, host=host, port=port)
    else:
        # Default STDIO transport
        mcp.run()
