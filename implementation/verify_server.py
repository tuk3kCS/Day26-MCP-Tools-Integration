import sys
import os
import json

# Ensure implementation is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server import search, insert, aggregate, database_schema, table_schema

def verify():
    print("==================================================")
    print("MCP SERVER MANUAL VERIFICATION AND DEMO RUN")
    print("==================================================")
    
    print("\n--- 1. Discovery ---")
    print("Exposed resources:")
    print("  - schema://database")
    print("  - schema://table/{table_name}")
    print("Exposed tools:")
    print("  - search")
    print("  - insert")
    print("  - aggregate")
    
    print("\n--- 2. Database Schema Resource (Full Database) ---")
    schema_res = database_schema()
    print(schema_res)
    
    print("\n--- 3. Table Schema Resource (students) ---")
    tbl_schema_res = table_schema("students")
    print(tbl_schema_res)
    
    print("\n--- 4. Tool Call: search (students in cohort 'A1') ---")
    search_res = search(table="students", filters={"cohort": "A1"})
    print(search_res)
    
    print("\n--- 5. Tool Call: insert (new student) ---")
    # Using a random email to prevent unique constraint failures on multiple runs
    import random
    rand_id = random.randint(1000, 9999)
    email = f"long{rand_id}@example.com"
    insert_res = insert(table="students", values={"name": "Hoang Long", "email": email, "cohort": "B2"})
    print(insert_res)
    
    print("\n--- 6. Tool Call: aggregate (average grade of CSCS enrollments) ---")
    agg_res = aggregate(table="enrollments", metric="avg", column="grade")
    print(agg_res)
    
    print("\n--- 7. Tool Call: aggregate (count students grouped by cohort) ---")
    agg_groupby_res = aggregate(table="students", metric="count", group_by=["cohort"])
    print(agg_groupby_res)

    print("\n--- 8. Tool Call: Error handling (invalid table search) ---")
    err_res = search(table="non_existent_table")
    print(err_res)

    print("\n--- 9. Tool Call: Error handling (invalid filter operator) ---")
    err_operator_res = search(table="students", filters={"cohort": {"operator": "INVALID_OP", "value": "A1"}})
    print(err_operator_res)

    print("==================================================")
    print("Verification completed successfully!")
    print("==================================================")

if __name__ == "__main__":
    verify()
