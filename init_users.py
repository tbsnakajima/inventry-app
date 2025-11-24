import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("stock.db")
cur = conn.cursor()

# users テーブル作成
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
""")

# 初期ユーザー作成
cur.execute("""
INSERT OR IGNORE INTO users (username, password, role)
VALUES (?, ?, ?)
""", ("owner", generate_password_hash("ownerpass"), "owner"))

cur.execute("""
INSERT OR IGNORE INTO users (username, password, role)
VALUES (?, ?, ?)
""", ("staff", generate_password_hash("staffpass"), "staff"))


conn.commit()
conn.close()

print("users テーブル作成と初期ユーザー作成完了")
