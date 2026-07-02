import os
import sqlite3
import sys

# Ensure parent directory is in path to import db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import SQLiteAdapter, PostgreSQLAdapter, get_adapter

SQLITE_SCHEMA = """
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
    semester TEXT NOT NULL,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
);
"""

SQLITE_SEED = """
-- Seed students
INSERT OR IGNORE INTO students (id, name, email, cohort) VALUES 
(1, 'Alice Nguyen', 'alice@example.com', 'A1'),
(2, 'Bob Tran', 'bob@example.com', 'A1'),
(3, 'Charlie Le', 'charlie@example.com', 'A2'),
(4, 'David Pham', 'david@example.com', 'B1'),
(5, 'Emma Hoang', 'emma@example.com', 'B1');

-- Seed courses
INSERT OR IGNORE INTO courses (id, title, code, instructor) VALUES
(1, 'Introduction to Computer Science', 'CS101', 'Dr. Son'),
(2, 'Database Systems', 'CS201', 'Dr. Hoa'),
(3, 'Web Development', 'CS301', 'Prof. Huy');

-- Seed enrollments
INSERT OR IGNORE INTO enrollments (id, student_id, course_id, grade, semester) VALUES
(1, 1, 1, 85.5, 'Fall 2025'),
(2, 1, 2, 90.0, 'Fall 2025'),
(3, 2, 1, 78.0, 'Fall 2025'),
(4, 2, 3, 92.5, 'Fall 2025'),
(5, 3, 2, 88.0, 'Fall 2025'),
(6, 4, 1, 95.0, 'Fall 2025'),
(7, 5, 3, 89.0, 'Fall 2025');
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    cohort VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    instructor VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    grade REAL,
    semester VARCHAR(50) NOT NULL
);
"""

POSTGRES_SEED = """
-- Seed students
INSERT INTO students (id, name, email, cohort) VALUES 
(1, 'Alice Nguyen', 'alice@example.com', 'A1'),
(2, 'Bob Tran', 'bob@example.com', 'A1'),
(3, 'Charlie Le', 'charlie@example.com', 'A2'),
(4, 'David Pham', 'david@example.com', 'B1'),
(5, 'Emma Hoang', 'emma@example.com', 'B1')
ON CONFLICT (email) DO NOTHING;

-- Seed courses
INSERT INTO courses (id, title, code, instructor) VALUES
(1, 'Introduction to Computer Science', 'CS101', 'Dr. Son'),
(2, 'Database Systems', 'CS201', 'Dr. Hoa'),
(3, 'Web Development', 'CS301', 'Prof. Huy')
ON CONFLICT (code) DO NOTHING;

-- Seed enrollments
INSERT INTO enrollments (id, student_id, course_id, grade, semester) VALUES
(1, 1, 1, 85.5, 'Fall 2025'),
(2, 1, 2, 90.0, 'Fall 2025'),
(3, 2, 1, 78.0, 'Fall 2025'),
(4, 2, 3, 92.5, 'Fall 2025'),
(5, 3, 2, 88.0, 'Fall 2025'),
(6, 4, 1, 95.0, 'Fall 2025'),
(7, 5, 3, 89.0, 'Fall 2025')
ON CONFLICT (id) DO NOTHING;

-- Reset serial sequences
SELECT setval('students_id_seq', COALESCE((SELECT MAX(id)+1 FROM students), 1), false);
SELECT setval('courses_id_seq', COALESCE((SELECT MAX(id)+1 FROM courses), 1), false);
SELECT setval('enrollments_id_seq', COALESCE((SELECT MAX(id)+1 FROM enrollments), 1), false);
"""

def create_database():
    adapter = get_adapter()
    if isinstance(adapter, SQLiteAdapter):
        print(f"Initializing SQLite database at: {adapter.db_path}")
        with sqlite3.connect(adapter.db_path) as conn:
            conn.executescript(SQLITE_SCHEMA)
            conn.executescript(SQLITE_SEED)
            conn.commit()
        print("SQLite database successfully initialized and seeded.")
        return adapter.db_path
    elif isinstance(adapter, PostgreSQLAdapter):
        print(f"Initializing PostgreSQL database...")
        conn = adapter.connect()
        with conn.cursor() as cursor:
            cursor.execute(POSTGRES_SCHEMA)
            cursor.execute(POSTGRES_SEED)
        conn.close()
        print("PostgreSQL database successfully initialized and seeded.")
        return adapter.connection_uri
    else:
        raise ValueError("Unknown database adapter type.")

if __name__ == "__main__":
    create_database()
