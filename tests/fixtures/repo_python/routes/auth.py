import sqlite3


def get_user_by_username(db_path: str, username: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Intentional unparameterized SQL query injection vulnerability
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()
