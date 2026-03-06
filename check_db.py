import sqlite3
import json

conn = sqlite3.connect(r'c:\Users\Diandra Riando\OneDrive\Documents\Capstone\Cursor Code\data\datalake.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print(f"Tables in datalake.db: {tables}")

for table in tables:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    
    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    for row in rows:
        for idx, col_val in enumerate(row):
            if isinstance(col_val, str) and ('</div>' in col_val or '<div' in col_val):
                print(f"FOUND HTML IN {table}.{columns[idx]}:")
                print(repr(col_val[:200] + "..."))
