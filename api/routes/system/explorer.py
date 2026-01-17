"""
Database Explorer Routes - Schema Introspection and Read-Only Queries
For administrative use only.
"""

import re
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import Dict, Any, List

from database.session import get_db, engine
from core.models import User
from core.security import require_admin

router = APIRouter(tags=["System Explorer"])


@router.get("/schema")
async def get_database_schema(
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Returns the complete database schema including tables, columns, and relationships.
    Uses SQLAlchemy Inspector for metadata reflection.

    Returns:
        - tables: List of table objects with columns and foreign keys
        - relationships: List of FK relationships for drawing edges
    """
    inspector = inspect(engine)

    tables = []
    relationships = []

    for table_name in inspector.get_table_names():
        # Get columns
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": False,  # Will be updated below
                "default": str(col.get("default")) if col.get("default") else None
            })

        # Mark primary keys
        pk_constraint = inspector.get_pk_constraint(table_name)
        pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []
        for col in columns:
            if col["name"] in pk_columns:
                col["primary_key"] = True

        # Get foreign keys
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            fk_info = {
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"],
                "name": fk.get("name")
            }
            foreign_keys.append(fk_info)

            # Add to relationships for edge drawing
            for i, col in enumerate(fk["constrained_columns"]):
                relationships.append({
                    "source_table": table_name,
                    "source_column": col,
                    "target_table": fk["referred_table"],
                    "target_column": fk["referred_columns"][i] if i < len(fk["referred_columns"]) else "id",
                    "constraint_name": fk.get("name")
                })

        # Get indexes
        indexes = []
        for idx in inspector.get_indexes(table_name):
            indexes.append({
                "name": idx["name"],
                "columns": idx["column_names"],
                "unique": idx.get("unique", False)
            })

        tables.append({
            "name": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "primary_key_columns": pk_columns
        })

    return {
        "tables": tables,
        "relationships": relationships,
        "table_count": len(tables),
        "relationship_count": len(relationships)
    }


# SQL keywords that are forbidden (write operations)
FORBIDDEN_SQL_PATTERNS = [
    r'\bDROP\b',
    r'\bDELETE\b',
    r'\bUPDATE\b',
    r'\bINSERT\b',
    r'\bTRUNCATE\b',
    r'\bALTER\b',
    r'\bCREATE\b',
    r'\bGRANT\b',
    r'\bREVOKE\b',
    r'\bEXEC\b',
    r'\bEXECUTE\b',
    r'--',  # SQL comments (potential injection)
    r'/\*',  # Block comments
]


def validate_readonly_query(sql: str) -> bool:
    """
    Validates that the SQL query is read-only.
    Returns True if safe, raises HTTPException if not.
    """
    # Normalize whitespace and convert to uppercase for checking
    normalized = ' '.join(sql.upper().split())

    # Must start with SELECT or WITH (for CTEs)
    if not (normalized.startswith('SELECT') or normalized.startswith('WITH')):
        raise HTTPException(
            status_code=400,
            detail="Query must start with SELECT or WITH"
        )

    # Check for forbidden patterns
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail=f"Query contains forbidden operation: {pattern.replace(chr(92), '')}"
            )

    return True


@router.post("/query")
async def execute_readonly_query(
    payload: Dict[str, Any] = Body(..., examples=[{"sql": "SELECT * FROM users LIMIT 10"}]),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Executes a read-only SQL query against the database.

    ADMIN ONLY - Restricted to SELECT queries.

    Args:
        payload: JSON with "sql" key containing the query

    Returns:
        - columns: List of column names
        - rows: List of row data as dictionaries
        - row_count: Number of rows returned
    """
    sql = payload.get("sql", "").strip()

    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required")

    # Validate the query is read-only
    validate_readonly_query(sql)

    # Add LIMIT if not present (safety measure)
    normalized = ' '.join(sql.upper().split())
    if 'LIMIT' not in normalized:
        sql = f"{sql} LIMIT 1000"

    try:
        result = db.execute(text(sql))

        # Get column names
        columns = list(result.keys())

        # Fetch all rows and convert to list of dicts
        rows = []
        for row in result.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convert non-serializable types to string
                if value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
                    value = str(value)
                row_dict[col] = value
            rows.append(row_dict)

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "query": sql
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Query execution error: {str(e)}"
        )


@router.get("/tables")
async def list_tables(
    current_user: User = Depends(require_admin)
) -> List[str]:
    """
    Returns a simple list of all table names in the database.
    Useful for autocomplete in the query editor.
    """
    inspector = inspect(engine)
    return inspector.get_table_names()


@router.get("/table/{table_name}")
async def get_table_preview(
    table_name: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Returns a preview of data from a specific table.

    Args:
        table_name: Name of the table to preview
        limit: Maximum number of rows (default 50, max 500)
    """
    inspector = inspect(engine)

    # Validate table exists
    if table_name not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    # Clamp limit
    limit = min(max(1, limit), 500)

    # Execute safe query
    sql = f'SELECT * FROM "{table_name}" LIMIT {limit}'

    try:
        result = db.execute(text(sql))
        columns = list(result.keys())

        rows = []
        for row in result.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                if value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
                    value = str(value)
                row_dict[col] = value
            rows.append(row_dict)

        # Get total count
        count_result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        total_count = count_result.scalar()

        return {
            "table_name": table_name,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "total_count": total_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading table: {str(e)}"
        )
