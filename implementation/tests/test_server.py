import os
import sys
import unittest
import json
import sqlite3

# Add parent directories to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SQLiteAdapter, ValidationError
from mcp_server import search, insert, aggregate, database_schema, table_schema

class TestMCPServer(unittest.TestCase):
    def setUp(self):
        # Create a clean test database for each test
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_sqlite_lab.db")
        os.environ["SQLITE_DB_PATH"] = self.db_path
        
        # Override adapter paths
        from db import get_adapter
        import mcp_server
        mcp_server.adapter = get_adapter()
        
        # Initialize test schema
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                cohort TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                instructor TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                grade REAL,
                semester TEXT NOT NULL
            );
            
            -- Seed test records
            INSERT OR IGNORE INTO students (id, name, email, cohort) VALUES 
            (1, 'Alice Nguyen', 'alice@example.com', 'A1'),
            (2, 'Bob Tran', 'bob@example.com', 'A1'),
            (3, 'Charlie Le', 'charlie@example.com', 'A2');
            
            INSERT OR IGNORE INTO courses (id, title, code, instructor) VALUES
            (1, 'Introduction to CS', 'CS101', 'Dr. Son');
            
            INSERT OR IGNORE INTO enrollments (id, student_id, course_id, grade, semester) VALUES
            (1, 1, 1, 85.5, 'Fall 2025'),
            (2, 2, 1, 75.0, 'Fall 2025');
            """)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        # Remove the test database file after each test
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_search_all_students(self):
        res = search(table="students")
        data = json.loads(res)
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["name"], "Alice Nguyen")

    def test_search_with_filter(self):
        res = search(table="students", filters={"cohort": "A1"})
        data = json.loads(res)
        self.assertEqual(len(data), 2)
        for row in data:
            self.assertEqual(row["cohort"], "A1")

    def test_search_with_complex_filter(self):
        res = search(table="enrollments", filters=[{"column": "grade", "operator": ">=", "value": 80.0}])
        data = json.loads(res)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["grade"], 85.5)

    def test_search_invalid_table(self):
        res = search(table="nonexistent")
        self.assertIn("Validation Error", res)
        self.assertIn("does not exist", res)

    def test_search_invalid_column(self):
        res = search(table="students", columns=["nonexistent"])
        self.assertIn("Validation Error", res)
        self.assertIn("do not exist", res)

    def test_insert_student(self):
        payload = {"name": "Test Student", "email": "test@example.com", "cohort": "A2"}
        res = insert(table="students", values=payload)
        data = json.loads(res)
        self.assertEqual(data["name"], "Test Student")
        self.assertEqual(data["email"], "test@example.com")
        self.assertTrue("id" in data)

    def test_insert_empty(self):
        res = insert(table="students", values={})
        self.assertIn("Validation Error", res)

    def test_insert_invalid_column(self):
        res = insert(table="students", values={"invalid_col": "val"})
        self.assertIn("Validation Error", res)

    def test_aggregate_count(self):
        res = aggregate(table="students", metric="count")
        data = json.loads(res)
        self.assertEqual(data[0]["value"], 3)

    def test_aggregate_avg(self):
        res = aggregate(table="enrollments", metric="avg", column="grade")
        data = json.loads(res)
        self.assertEqual(data[0]["value"], 80.25) # (85.5 + 75.0) / 2

    def test_aggregate_group_by(self):
        res = aggregate(table="students", metric="count", group_by=["cohort"])
        data = json.loads(res)
        # cohort A1 should have 2, A2 should have 1
        cohort_counts = {row["cohort"]: row["value"] for row in data}
        self.assertEqual(cohort_counts["A1"], 2)
        self.assertEqual(cohort_counts["A2"], 1)

    def test_aggregate_invalid_metric(self):
        res = aggregate(table="students", metric="invalid_metric")
        self.assertIn("Validation Error", res)

    def test_aggregate_missing_column(self):
        res = aggregate(table="students", metric="avg")
        self.assertIn("Validation Error", res)

    def test_database_schema_resource(self):
        res = database_schema()
        schema = json.loads(res)
        self.assertIn("students", schema)
        self.assertIn("courses", schema)
        self.assertIn("enrollments", schema)
        self.assertIn("name", schema["students"])

    def test_table_schema_resource(self):
        res = table_schema("students")
        schema = json.loads(res)
        self.assertIn("students", schema)
        self.assertIn("name", schema["students"])

    def test_table_schema_resource_invalid(self):
        res = table_schema("nonexistent")
        self.assertIn("Validation Error", res)

if __name__ == "__main__":
    unittest.main()
