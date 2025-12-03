import sqlite3
from werkzeug.security import generate_password_hash

# DB 作成・接続
conn = sqlite3.connect("inventory.db")
cur = conn.cursor()

# 外部キー有効化
cur.execute("PRAGMA foreign_keys = ON;")

# ---------------------------
# テーブル作成
# ---------------------------

# 1. 品目マスタ
cur.execute("""
CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    category TEXT,
    unit TEXT,
    reorder_point INTEGER,
    standard_price REAL
)
""")

# 2. 仕入先マスタ
cur.execute("""
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    contact TEXT,
    email TEXT,
    address TEXT
)
""")

# 3. 在庫テーブル（修正版）
cur.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    ordered INTEGER DEFAULT 0,
    allocated INTEGER DEFAULT 0,
    last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
    expiration_date DATE,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
)
""")

# 4. 入庫履歴
cur.execute("""
CREATE TABLE IF NOT EXISTS stockin (
    stockin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    date DATETIME DEFAULT CURRENT_TIMESTAMP,
    expiration_date DATE,
    FOREIGN KEY (item_id) REFERENCES items(item_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
)
""")

# 5. 出庫履歴
cur.execute("""
CREATE TABLE IF NOT EXISTS stockout (
    stockout_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    date DATETIME DEFAULT CURRENT_TIMESTAMP,
    usage TEXT,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
)
""")

# 6. 発注履歴
cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    FOREIGN KEY (item_id) REFERENCES items(item_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
)
""")

# 7. ユーザー管理
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
""")

# 8. 出庫予約テーブル（コメント削除済）
cur.execute("""
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    reserved_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    expected_use_date DATE,
    usage TEXT,
    status TEXT DEFAULT 'reserved',
    FOREIGN KEY (item_id) REFERENCES items(item_id)
)
""")

# ---------------------------
# 初期ユーザー作成
# ---------------------------
cur.execute("""
INSERT OR IGNORE INTO users (username, password, role)
VALUES (?, ?, ?)
""", ("owner", generate_password_hash("ownerpass"), "owner"))

cur.execute("""
INSERT OR IGNORE INTO users (username, password, role)
VALUES (?, ?, ?)
""", ("staff", generate_password_hash("staffpass"), "staff"))

# ---------------------------
# 保存・終了
# ---------------------------
conn.commit()
conn.close()

print("inventory.db 作成完了、全テーブルと初期ユーザーも追加されました")
