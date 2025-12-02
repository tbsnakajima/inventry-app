from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret_key_here"  # セッション用

# DB接続
def get_db():
    conn = sqlite3.connect("inventory.db")
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

# --- 在庫取得 ---
@app.route("/stock", methods=["GET"])
def get_stock():
    conn = get_db()
    cur = conn.cursor()
    # inventory と items を結合して unit と reorder_point 取得
    cur.execute("""
        SELECT inv.inventory_id,
               it.item_name,
               it.unit,
               inv.quantity,
               it.reorder_point,
               CASE WHEN inv.quantity <= it.reorder_point THEN 1 ELSE 0 END AS reorder_flag
        FROM inventory AS inv
        JOIN items AS it ON inv.item_id = it.item_id
    """)
    rows = cur.fetchall()
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
