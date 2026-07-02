import abc
import os
import sqlite3
import logging
import contextlib
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("mcp_db_server")

class ValidationError(Exception):
    """Raised when a validation check fails (e.g. unknown table/column, invalid operator)."""
    pass

class DatabaseAdapter(abc.ABC):
    @abc.abstractmethod
    def connect(self):
        pass

    @contextlib.contextmanager
    def connection(self):
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @abc.abstractmethod
    def list_tables(self) -> List[str]:
        pass

    @abc.abstractmethod
    def get_table_schema(self, table: str) -> Dict[str, str]:
        """Returns dict of column_name: type."""
        pass

    @abc.abstractmethod
    def search(
        self,
        table: str,
        columns: Optional[List[str]] = None,
        filters: Optional[Any] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False
    ) -> List[Dict[str, Any]]:
        pass

    @abc.abstractmethod
    def insert(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abc.abstractmethod
    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[Any] = None,
        group_by: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        pass

    def validate_table(self, table: str):
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"Table '{table}' does not exist. Available tables: {', '.join(tables)}")

    def validate_columns(self, table: str, columns: List[str]):
        schema = self.get_table_schema(table)
        invalid = [col for col in columns if col not in schema]
        if invalid:
            raise ValidationError(f"Columns {invalid} do not exist in table '{table}'. Available columns: {', '.join(schema.keys())}")

    def _placeholder(self, name: str) -> str:
        raise NotImplementedError

    def _parse_filters(self, table: str, filters: Any) -> List[Tuple[str, str, Any]]:
        parsed = []
        if not filters:
            return parsed

        schema = self.get_table_schema(table)
        allowed_ops = {"=", "!=", "<", ">", "<=", ">=", "LIKE", "IN"}

        if isinstance(filters, dict):
            for col, val in filters.items():
                if col not in schema:
                    raise ValidationError(f"Invalid filter: Column '{col}' does not exist in table '{table}'.")
                if isinstance(val, dict):
                    # Format: {"grade": {">=": 85}} or {"grade": {"operator": ">=", "value": 85}}
                    has_operator = False
                    for op, op_val in val.items():
                        op_upper = op.upper()
                        if op_upper == "OPERATOR" and "value" in val:
                            op_str = val["operator"].upper()
                            real_val = val["value"]
                            if op_str not in allowed_ops:
                                raise ValidationError(f"Unsupported filter operator: '{op_str}'. Supported: {list(allowed_ops)}")
                            parsed.append((col, op_str, real_val))
                            has_operator = True
                            break
                        elif op_upper in allowed_ops:
                            parsed.append((col, op_upper, op_val))
                            has_operator = True
                    if not has_operator:
                        raise ValidationError(f"Invalid nested filter for '{col}'. Must specify operator.")
                else:
                    # Implicit =
                    parsed.append((col, "=", val))

        elif isinstance(filters, list):
            for item in filters:
                if not isinstance(item, dict):
                    raise ValidationError("Filters list must contain filter objects (dictionaries).")
                col = item.get("column")
                op = item.get("operator", "=").upper()
                val = item.get("value")
                if not col:
                    raise ValidationError("Filter item must specify 'column'.")
                if col not in schema:
                    raise ValidationError(f"Invalid filter: Column '{col}' does not exist in table '{table}'.")
                if op not in allowed_ops:
                    raise ValidationError(f"Unsupported filter operator: '{op}'. Supported: {list(allowed_ops)}")
                parsed.append((col, op, val))
        else:
            raise ValidationError("Filters must be a dictionary or a list.")

        return parsed


class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _placeholder(self, name: str) -> str:
        return f":{name}"

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def list_tables(self) -> List[str]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            return [row["name"] for row in cursor.fetchall()]

    def get_table_schema(self, table: str) -> Dict[str, str]:
        # Validate table is in the database (guards against injection in PRAGMA table_info)
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"Table '{table}' does not exist.")

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table});")
            rows = cursor.fetchall()
            return {row["name"]: row["type"] for row in rows}

    def search(
        self,
        table: str,
        columns: Optional[List[str]] = None,
        filters: Optional[Any] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False
    ) -> List[Dict[str, Any]]:
        self.validate_table(table)
        schema = self.get_table_schema(table)

        if not columns:
            columns = list(schema.keys())
        else:
            self.validate_columns(table, columns)

        parsed_filters = self._parse_filters(table, filters)

        cols_str = ", ".join(columns)
        sql = f"SELECT {cols_str} FROM {table}"

        where_clauses = []
        params = {}
        for i, (col, op, val) in enumerate(parsed_filters):
            param_name = f"f_{col}_{i}"
            if op == "IN":
                if not isinstance(val, (list, tuple)):
                    raise ValidationError(f"Filter value for IN operator must be a list or tuple. Got {type(val)}")
                if not val:
                    where_clauses.append("1 = 0")
                else:
                    in_placeholders = []
                    for j, v in enumerate(val):
                        sub_param = f"{param_name}_{j}"
                        in_placeholders.append(self._placeholder(sub_param))
                        params[sub_param] = v
                    placeholders_str = ", ".join(in_placeholders)
                    where_clauses.append(f"{col} IN ({placeholders_str})")
            else:
                placeholder = self._placeholder(param_name)
                where_clauses.append(f"{col} {op} {placeholder}")
                params[param_name] = val

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if order_by:
            if order_by not in schema:
                raise ValidationError(f"Order by column '{order_by}' does not exist in table '{table}'.")
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {order_by} {direction}"

        if not isinstance(limit, int) or limit < 0:
            raise ValidationError("Limit must be a non-negative integer.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer.")

        limit = min(limit, 100)

        sql += f" LIMIT {limit} OFFSET {offset}"

        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
            except Exception as e:
                raise ValidationError(f"Database query failed: {str(e)}")

    def insert(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_table(table)
        schema = self.get_table_schema(table)

        if not values:
            raise ValidationError("Insert request must contain at least one column-value pair.")

        self.validate_columns(table, list(values.keys()))

        cols = list(values.keys())
        placeholders = [self._placeholder(col) for col in cols]
        
        cols_str = ", ".join(cols)
        places_str = ", ".join(placeholders)
        
        sql = f"INSERT INTO {table} ({cols_str}) VALUES ({places_str});"

        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, values)
                inserted_id = cursor.lastrowid
                conn.commit()
            except Exception as e:
                raise ValidationError(f"Insert failed: {str(e)}")

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table});")
            pk_cols = [row["name"] for row in cursor.fetchall() if row["pk"] > 0]
        
        if len(pk_cols) == 1 and pk_cols[0] in schema and inserted_id is not None:
            sql_fetch = f"SELECT * FROM {table} WHERE {pk_cols[0]} = :pk_val"
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_fetch, {"pk_val": inserted_id})
                row = cursor.fetchone()
                if row:
                    return dict(row)

        result = dict(values)
        if inserted_id is not None and len(pk_cols) == 1:
            result[pk_cols[0]] = inserted_id
        return result

    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[Any] = None,
        group_by: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        self.validate_table(table)
        schema = self.get_table_schema(table)

        metric_upper = metric.upper()
        allowed_metrics = {"COUNT", "AVG", "SUM", "MIN", "MAX"}
        if metric_upper not in allowed_metrics:
            raise ValidationError(f"Unsupported metric: '{metric}'. Supported: {list(allowed_metrics)}")

        if metric_upper != "COUNT" and not column:
            raise ValidationError(f"Metric '{metric}' requires a column name.")

        if column:
            self.validate_columns(table, [column])
            agg_expr = f"{metric_upper}({column})"
        else:
            agg_expr = "COUNT(*)"

        select_cols = []
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            self.validate_columns(table, group_by)
            select_cols.extend(group_by)

        select_cols.append(f"{agg_expr} AS value")
        
        sql = f"SELECT {', '.join(select_cols)} FROM {table}"

        parsed_filters = self._parse_filters(table, filters)
        where_clauses = []
        params = {}
        for i, (col, op, val) in enumerate(parsed_filters):
            param_name = f"f_{col}_{i}"
            if op == "IN":
                if not isinstance(val, (list, tuple)):
                    raise ValidationError(f"Filter value for IN operator must be a list or tuple. Got {type(val)}")
                if not val:
                    where_clauses.append("1 = 0")
                else:
                    in_placeholders = []
                    for j, v in enumerate(val):
                        sub_param = f"{param_name}_{j}"
                        in_placeholders.append(self._placeholder(sub_param))
                        params[sub_param] = v
                    placeholders_str = ", ".join(in_placeholders)
                    where_clauses.append(f"{col} IN ({placeholders_str})")
            else:
                placeholder = self._placeholder(param_name)
                where_clauses.append(f"{col} {op} {placeholder}")
                params[param_name] = val

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if group_by:
            sql += f" GROUP BY {', '.join(group_by)}"

        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
            except Exception as e:
                raise ValidationError(f"Aggregate query failed: {str(e)}")


class PostgreSQLAdapter(DatabaseAdapter):
    def __init__(self, connection_uri: str):
        self.connection_uri = connection_uri

    def _placeholder(self, name: str) -> str:
        return f"%({name})s"

    def connect(self):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(self.connection_uri)
        conn.autocommit = True
        return conn

    def list_tables(self) -> List[str]:
        sql = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE';
        """
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return [row[0] for row in cursor.fetchall()]

    def get_table_schema(self, table: str) -> Dict[str, str]:
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"Table '{table}' does not exist.")

        sql = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = %s;
        """
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (table,))
                return {row[0]: row[1] for row in cursor.fetchall()}

    def search(
        self,
        table: str,
        columns: Optional[List[str]] = None,
        filters: Optional[Any] = None,
        limit: int = 20,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = False
    ) -> List[Dict[str, Any]]:
        self.validate_table(table)
        schema = self.get_table_schema(table)

        if not columns:
            columns = list(schema.keys())
        else:
            self.validate_columns(table, columns)

        parsed_filters = self._parse_filters(table, filters)

        cols_str = ", ".join([f'"{c}"' for c in columns])
        sql = f'SELECT {cols_str} FROM "{table}"'

        where_clauses = []
        params = {}
        for i, (col, op, val) in enumerate(parsed_filters):
            param_name = f"f_{col}_{i}"
            if op == "IN":
                if not isinstance(val, (list, tuple)):
                    raise ValidationError(f"Filter value for IN operator must be a list or tuple. Got {type(val)}")
                if not val:
                    where_clauses.append("1 = 0")
                else:
                    in_placeholders = []
                    for j, v in enumerate(val):
                        sub_param = f"{param_name}_{j}"
                        in_placeholders.append(self._placeholder(sub_param))
                        params[sub_param] = v
                    placeholders_str = ", ".join(in_placeholders)
                    where_clauses.append(f'"{col}" IN ({placeholders_str})')
            else:
                placeholder = self._placeholder(param_name)
                where_clauses.append(f'"{col}" {op} {placeholder}')
                params[param_name] = val

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if order_by:
            if order_by not in schema:
                raise ValidationError(f"Order by column '{order_by}' does not exist in table '{table}'.")
            direction = "DESC" if descending else "ASC"
            sql += f' ORDER BY "{order_by}" {direction}'

        if not isinstance(limit, int) or limit < 0:
            raise ValidationError("Limit must be a non-negative integer.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer.")

        limit = min(limit, 100)
        sql += f" LIMIT {limit} OFFSET {offset}"

        import psycopg2.extras
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, params)
                    return [dict(row) for row in cursor.fetchall()]
                except Exception as e:
                    raise ValidationError(f"Database query failed: {str(e)}")

    def insert(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_table(table)
        schema = self.get_table_schema(table)

        if not values:
            raise ValidationError("Insert request must contain at least one column-value pair.")

        self.validate_columns(table, list(values.keys()))

        cols = list(values.keys())
        cols_escaped = ", ".join([f'"{c}"' for c in cols])
        placeholders = [self._placeholder(col) for col in cols]
        places_str = ", ".join(placeholders)

        sql = f'INSERT INTO "{table}" ({cols_escaped}) VALUES ({places_str}) RETURNING *;'

        import psycopg2.extras
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, values)
                    row = cursor.fetchone()
                    return dict(row) if row else values
                except Exception as e:
                    raise ValidationError(f"Insert failed: {str(e)}")

    def aggregate(
        self,
        table: str,
        metric: str,
        column: Optional[str] = None,
        filters: Optional[Any] = None,
        group_by: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        self.validate_table(table)
        schema = self.get_table_schema(table)

        metric_upper = metric.upper()
        allowed_metrics = {"COUNT", "AVG", "SUM", "MIN", "MAX"}
        if metric_upper not in allowed_metrics:
            raise ValidationError(f"Unsupported metric: '{metric}'. Supported: {list(allowed_metrics)}")

        if metric_upper != "COUNT" and not column:
            raise ValidationError(f"Metric '{metric}' requires a column name.")

        if column:
            self.validate_columns(table, [column])
            agg_expr = f'{metric_upper}("{column}")'
        else:
            agg_expr = "COUNT(*)"

        select_cols = []
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            self.validate_columns(table, group_by)
            select_cols.extend([f'"{g}"' for g in group_by])

        select_cols.append(f"{agg_expr} AS value")

        sql = f'SELECT {", ".join(select_cols)} FROM "{table}"'

        parsed_filters = self._parse_filters(table, filters)
        where_clauses = []
        params = {}
        for i, (col, op, val) in enumerate(parsed_filters):
            param_name = f"f_{col}_{i}"
            if op == "IN":
                if not isinstance(val, (list, tuple)):
                    raise ValidationError(f"Filter value for IN operator must be a list or tuple. Got {type(val)}")
                if not val:
                    where_clauses.append("1 = 0")
                else:
                    in_placeholders = []
                    for j, v in enumerate(val):
                        sub_param = f"{param_name}_{j}"
                        in_placeholders.append(self._placeholder(sub_param))
                        params[sub_param] = v
                    placeholders_str = ", ".join(in_placeholders)
                    where_clauses.append(f'"{col}" IN ({placeholders_str})')
            else:
                placeholder = self._placeholder(param_name)
                where_clauses.append(f'"{col}" {op} {placeholder}')
                params[param_name] = val

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if group_by:
            sql += f' GROUP BY {", ".join([f'"{g}"' for g in group_by])}'

        import psycopg2.extras
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, params)
                    return [dict(row) for row in cursor.fetchall()]
                except Exception as e:
                    raise ValidationError(f"Aggregate query failed: {str(e)}")


def get_adapter() -> DatabaseAdapter:
    pg_uri = os.environ.get("DATABASE_URL")
    if pg_uri:
        logger.info("Using PostgreSQLAdapter with DATABASE_URL")
        return PostgreSQLAdapter(pg_uri)
    
    db_path = os.environ.get("SQLITE_DB_PATH", "sqlite_lab.db")
    if not os.path.isabs(db_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, db_path)
    
    logger.info(f"Using SQLiteAdapter with db_path: {db_path}")
    return SQLiteAdapter(db_path)
