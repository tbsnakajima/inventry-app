from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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
    return render_template("index.html")

# --- 品目追加 ---
@app.route("/item/add", methods=["POST"])
@role_required("owner", "manager")
def add_item():
    data = request.json
    item_name = data.get("item_name")
    category = data.get("category", "")
    unit = data.get("unit", "")
    reorder_point = data.get("reorder_point", 0)
    standard_price = data.get("standard_price", 0.0)

    conn = get_db()
    cur = conn.cursor()

    try:
        # --- 重複チェック ---
        cur.execute("SELECT item_id FROM items WHERE item_name = ?", (item_name,))
        if cur.fetchone():
            return jsonify({"status": "error", "message": "同じ商品名が既に存在します"}), 400

        # --- items に追加 ---
        cur.execute("""
            INSERT INTO items (item_name, category, unit, reorder_point, standard_price)
            VALUES (?, ?, ?, ?, ?)
        """, (item_name, category, unit, reorder_point, standard_price))

        # --- 追加した item_id を取得 ---
        item_id = cur.lastrowid

        # --- inventory に初期在庫作成 ---
        cur.execute("""
            INSERT INTO inventory (item_id, quantity)
            VALUES (?, ?)
        """, (item_id, 0))

        conn.commit()
        return jsonify({"status": "ok", "item_id": item_id})

    except sqlite3.IntegrityError as e:
        # DB 側の UNIQUE 制約に違反した場合の保険
        return jsonify({"status": "error", "message": "同じ商品名が既に存在します"}), 400

    finally:
        conn.close()


# --- 在庫取得（発注フラグ含む） ---
@app.route("/stock", methods=["GET"])
def get_stock():
    conn = get_db()
    cur = conn.cursor()
    
    # inventory と items を結合して必要な情報を取得
    cur.execute("""
        SELECT inv.inventory_id,
               it.item_name,
               it.category,
               it.unit,
               inv.quantity,
               it.reorder_point,
               CASE WHEN inv.quantity <= it.reorder_point THEN 1 ELSE 0 END AS reorder_flag
        FROM inventory AS inv
        JOIN items AS it ON inv.item_id = it.item_id
    """)
    
    rows = cur.fetchall()
    conn.close()  # 忘れずに閉じる
    
    # JSON に変換して返す
    return jsonify([dict(row) for row in rows])

# --- 入庫処理 ---
@app.route("/stock/in", methods=["POST"])
@role_required("owner", "manager")
def stock_in():
    data = request.json
    inventory_id = data["inventory_id"]
    qty = data["qty"]

    conn = get_db()
    cur = conn.cursor()

    # 在庫更新（入庫なのでプラス）
    cur.execute("UPDATE inventory SET quantity = quantity + ? WHERE inventory_id = ?", (qty, inventory_id))

    # 入庫履歴追加
    cur.execute("""
        INSERT INTO stockin (item_id, supplier_id, quantity, date)
        SELECT item_id, 1, ?, datetime('now')  -- supplier_id は仮に 1
        FROM inventory
        WHERE inventory_id = ?
    """, (qty, inventory_id))

    conn.commit()
    return jsonify({"status": "ok"})


# --- 出庫処理 ---
@app.route("/stock/out", methods=["POST"])
@role_required("owner", "manager")
def stock_out():
    data = request.json
    inventory_id = data["inventory_id"]
    qty = data["qty"]

    conn = get_db()
    cur = conn.cursor()

    # 在庫更新（出庫なのでマイナス）
    cur.execute("UPDATE inventory SET quantity = quantity - ? WHERE inventory_id = ?", (qty, inventory_id))

    # 出庫履歴追加
    cur.execute("""
        INSERT INTO stockout (item_id, quantity, date, usage)
        SELECT item_id, ?, datetime('now'), '消費'
        FROM inventory
        WHERE inventory_id = ?
    """, (qty, inventory_id))

    conn.commit()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
