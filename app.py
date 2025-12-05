from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "inventory.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

app = Flask(__name__)
app.secret_key = "secret_key_here"  # セッション用

# DB接続
def get_db():
    conn = sqlite3.connect("inventory.db",timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

# 権限デコレーター
def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if session['role'] not in roles:
                return "権限がありません", 403
            return f(*args, **kwargs)
        return decorated
    return wrapper

@app.route("/dbcheck")
def dbcheck():
    import os
    return jsonify({"DB_PATH": DB_PATH, "exists": os.path.exists(DB_PATH)})


# --- ログイン ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("index"))
        return "ユーザー名またはパスワードが間違っています"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")

# --- 品目追加 ---
@app.route("/item/add", methods=["POST"])
@role_required("owner", "manager")
def add_item():
    data = request.json
    print("POST data:", data)
    
    item_name = data.get("item_name")
    category = data.get("category", "")
    unit = data.get("unit", "")
    reorder_point = int(data.get("reorder_point", 0))
    standard_price = float(data.get("standard_price", 0.0))

    conn = get_db()
    cur = conn.cursor()

    try:
        # 重複チェック
        cur.execute("SELECT item_id FROM items WHERE item_name = ?", (item_name,))
        if cur.fetchone():
            print("重複商品名:", item_name)
            return jsonify({"status": "error", "message": "同じ商品名が既に存在します"}), 400

        # items に追加
        cur.execute("""
            INSERT INTO items (item_name, category, unit, reorder_point, standard_price)
            VALUES (?, ?, ?, ?, ?)
        """, (item_name, category, unit, reorder_point, standard_price))
        item_id = cur.lastrowid
        print("追加 item_id:", item_id)

        # inventory に初期在庫作成
        cur.execute("""
            INSERT INTO inventory (item_id, quantity)
            VALUES (?, ?)
        """, (item_id, 0))

        conn.commit()
        print("DB commit 成功")
        return jsonify({"status": "ok", "item_id": item_id})

    except Exception as e:
        print("例外発生:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        conn.close()


# --- 予約作成 ---
@app.route("/reservation/create", methods=["POST"])
@role_required("owner", "manager")
def create_reservation():
    data = request.json
    inventory_id = data["inventory_id"]
    qty = data["qty"]
    usage = data.get("usage", "")

    conn = get_db()
    cur = conn.cursor()

    # 在庫情報取得
    cur.execute("SELECT item_id, quantity, allocated FROM inventory WHERE inventory_id = ?", (inventory_id,))
    inv = cur.fetchone()
    if not inv:
        conn.close()
        return jsonify({"status": "error", "message": "在庫が存在しません"}), 404

    available = inv["quantity"] - (inv["allocated"] or 0)
    if qty > available:
        conn.close()
        return jsonify({"status": "error", "message": f"可用在庫不足（{available}）"}), 400

    # reservation に追加
    cur.execute("""
        INSERT INTO reservations (item_id, quantity, usage)
        VALUES (?, ?, ?)
    """, (inv["item_id"], qty, usage))

    # inventory の allocated を更新
    cur.execute("""
        UPDATE inventory
        SET allocated = COALESCE(allocated,0) + ?
        WHERE inventory_id = ?
    """, (qty, inventory_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# --- 在庫取得（入荷待ち・予約割当・可用在庫を含む） ---
@app.route("/stock", methods=["GET"])
def get_stock():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            inv.inventory_id,
            it.item_name,
            it.category,
            it.unit,
            inv.quantity,
            COALESCE(inv.allocated,0) AS allocated,
            COALESCE(inv.ordered,0) AS ordered,
            (inv.quantity - COALESCE(inv.allocated,0)) AS available,
            CASE WHEN inv.quantity <= it.reorder_point THEN 1 ELSE 0 END AS reorder_flag
        FROM inventory AS inv
        JOIN items AS it ON inv.item_id = it.item_id
    """)
    
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


    # JSON に変換して返す
    result = []
    for row in rows:
        result.append({
            "inventory_id": row["inventory_id"],
            "item_name": row["item_name"],
            "category": row["category"],
            "unit": row["unit"],
            "quantity": row["quantity"],
            "allocated": row["allocated"],
            "ordered": row["ordered"],
            "available": row["available"],
            "reorder_flag": row["reorder_flag"]
        })

    return jsonify(result)

# --- 入庫処理 ---
@app.route("/stock/in", methods=["POST"])
@role_required("owner", "manager")
def stock_in():
    data = request.json
    inventory_id = data["inventory_id"]
    qty = data["qty"]

    conn = get_db()
    cur = conn.cursor()

    # 在庫取得
    cur.execute("SELECT item_id, quantity, ordered, allocated FROM inventory WHERE inventory_id = ?", (inventory_id,))
    inv = cur.fetchone()
    if not inv:
        conn.close()
        return jsonify({"status": "error", "message": "在庫が見つかりません"}), 404

    item_id = inv["item_id"]
    new_qty = inv["quantity"] + qty
    new_ordered = max(inv["ordered"] - qty, 0)

    # --- inventory 更新 ---
    cur.execute("UPDATE inventory SET quantity = quantity + ? WHERE inventory_id = ?", (qty, inventory_id))


    # --- stockin 履歴 ---
    cur.execute("""
        INSERT INTO stockin (item_id, supplier_id, quantity, date)
        VALUES (?, 1, ?, datetime('now'))
    """, (item_id, qty))

    # --- 予約割当の自動割当 ---
    cur.execute("""
        SELECT reservation_id, quantity, status
        FROM reservations
        WHERE item_id = ? AND status = 'reserved'
        ORDER BY reserved_date
    """, (item_id,))
    reservations = cur.fetchall()
    remaining = qty

    for r in reservations:
        if remaining <= 0:
            break
        allocate_qty = min(remaining, r["quantity"])
        # allocated 更新
        cur.execute("UPDATE inventory SET allocated = allocated + ? WHERE inventory_id = ?", (allocate_qty, inventory_id))
        # 予約数量更新（消化済みに変更する場合は status を 'consumed' に）
        cur.execute("""
            UPDATE reservations
            SET quantity = quantity - ?, status = CASE WHEN quantity - ? <= 0 THEN 'consumed' ELSE 'reserved' END
            WHERE reservation_id = ?
        """, (allocate_qty, allocate_qty, r["reservation_id"]))
        remaining -= allocate_qty

    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "ordered_remaining": new_ordered})


# --- 出庫処理 ---
@app.route("/stock/out", methods=["POST"])
@role_required("owner", "manager")
def stock_out():
    data = request.json
    inventory_id = data["inventory_id"]
    qty = data["qty"]

    conn = get_db()
    cur = conn.cursor()

    # 在庫取得
    cur.execute("SELECT quantity, allocated, item_id FROM inventory WHERE inventory_id = ?", (inventory_id,))
    inv = cur.fetchone()
    if not inv:
        return jsonify({"status": "error", "message": "在庫が見つかりません"}), 404

    available_qty = inv["quantity"] - inv["allocated"]
    if qty > available_qty:
        return jsonify({"status": "error", "message": f"出庫可能在庫不足 ({available_qty} 利用可能)"}), 400

    # allocated があれば減らす
    new_allocated = max(inv["allocated"] - qty, 0)

    # quantity 更新（総在庫は減らす）
    cur.execute("UPDATE inventory SET quantity = quantity - ? WHERE inventory_id = ?", (qty, inventory_id))


    # 出庫履歴追加
    cur.execute("""
        INSERT INTO stockout (item_id, quantity, date, usage)
        VALUES (?, ?, datetime('now'), '消費')
    """, (inv["item_id"], qty))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "allocated_remaining": new_allocated})

# DB 初期化スクリプト
def init_db():
    conn = sqlite3.connect("inventory.db")
    cur = conn.cursor()

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




if __name__ == "__main__":
    app.run(debug=True)
