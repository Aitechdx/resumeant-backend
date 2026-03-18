import os, sqlite3
DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, premium INTEGER DEFAULT 0, uses INTEGER DEFAULT 0)"
    )
    return conn

def get_user(user_id: str):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id,premium,uses FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.execute("INSERT INTO users(id,premium,uses) VALUES(?,?,?)", (user_id,0,0))
        conn.commit()
        return {"id": user_id, "premium": 0, "uses": 0}
    return {"id": row[0], "premium": row[1], "uses": row[2]}

def bump_use(user_id: str):
    conn = get_conn()
    conn.execute("UPDATE users SET uses = uses + 1 WHERE id=?", (user_id,))
    conn.commit()

def set_premium(user_id: str, value: int = 1):
    conn = get_conn()
    conn.execute("UPDATE users SET premium=? WHERE id=?", (value, user_id))
    conn.commit()
