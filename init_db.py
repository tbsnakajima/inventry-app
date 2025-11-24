import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("stock.db")
cur = conn.cursor()

# --- stockテーブル（最新版） ---
cur.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL,
    name TEXT,
    qty INTEGER NOT NULL,
    reorder_point INTEGER DEFAULT 0,
    min_qty INTEGER DEFAULT 0
)
""")

# --- historyテーブル ---
cur.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT,
    item TEXT,
    qty INTEGER,
    action TEXT
)
""")

# 初期データ
cur.execute("INSERT INTO stock (item, name, qty, reorder_point, min_qty) VALUES ('A001','コーヒー',10,5,1)")
cur.execute("INSERT INTO stock (item, name, qty, reorder_point, min_qty) VALUES ('B002','紅茶',3,5,1)")

# users テーブル作成
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
""")

# 初期ユーザー作成（例：オーナー）
cur.execute("""
INSERT OR IGNORE INTO users (username, password, role)
VALUES (?, ?, ?)
""", ("owner", generate_password_hash("ownerpass"), "owner"))

conn.commit()
conn.close()

print("users テーブル作成と初期ユーザー作成完了")