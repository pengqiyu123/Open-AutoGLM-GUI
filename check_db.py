"""Check database content for Mental Shortcut System."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "logs" / "tasks.db"
print(f"Database path: {db_path}")
print(f"Exists: {db_path.exists()}")

if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    # List all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nTables: {tables}")
    
    # Check mental_shortcuts table
    if "mental_shortcuts" in tables:
        print("\n=== Mental Shortcuts Table ===")
        
        # First check table structure
        cur.execute("PRAGMA table_info(mental_shortcuts)")
        columns = cur.fetchall()
        print("Columns:", [c[1] for c in columns])
        
        cur.execute("SELECT COUNT(*) FROM mental_shortcuts")
        count = cur.fetchone()[0]
        print(f"Total shortcuts: {count}")
        
        if count > 0:
            cur.execute("SELECT * FROM mental_shortcuts ORDER BY id DESC LIMIT 10")
            rows = cur.fetchall()
            col_names = [c[1] for c in columns]
            print("\nRecent shortcuts:")
            for row in rows:
                print("-" * 50)
                for i, val in enumerate(row):
                    print(f"  {col_names[i]}: {val}")
                print()
    else:
        print("\nmental_shortcuts table not found!")
    
    # Check recent tasks
    print("\n=== Recent Tasks ===")
    cur.execute("""
        SELECT session_id, timestamp, task_description, final_status, total_steps
        FROM tasks 
        ORDER BY timestamp DESC 
        LIMIT 3
    """)
    for row in cur.fetchall():
        print(f"  Session: {row[0][:20]}...")
        print(f"    Time: {row[1]}")
        print(f"    Task: {row[2][:50]}...")
        print(f"    Status: {row[3]}, Steps: {row[4]}")
        print()
    
    conn.close()
