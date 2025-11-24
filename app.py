from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
import sqlite3
from datetime import datetime
from flask import request, session, redirect, url_for, abort
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "secret_key_here"  # セッション用

def get_db():
    conn = sqlite3.connect("stock.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- 権限デコレーター ---
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
        if user and check_password_hash(user[2], password):
            session["user"] = user[1]
            session["role"] = user[3]
            return redirect(url_for("index"))
        else:
            return "ユーザー名またはパスワードが間違っています"
    return """
    <form method="post">
        ユーザー名: <input name="username"><br>
        パスワード: <input type="password" name="password"><br>
        <input type="submit" value="ログイン">
    </form>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    return render_template("index.html")
# --- 在庫取得（発注フラグ含む） ---
@app.route("/stock", methods=["GET"])
def get_stock():
    conn = get_db()
    cur = conn.cursor()
    # reorder_point が存在する前提 発注フラグ
    cur.execute("""
        SELECT *,
               CASE WHEN qty <= reorder_point THEN 1 ELSE 0 END AS reorder_flag
        FROM stock
    """)
    rows = cur.fetchall()
    return jsonify([dict(row) for row in rows])

# --- 入庫処理 ---
@app.route("/stock/in", methods=["POST"])
@role_required("owner", "manager")
def stock_in():
    data = request.json
    item = data["item"]
    qty = data["qty"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE stock SET qty = qty + ? WHERE item = ?", (qty, item))
    cur.execute(
        "INSERT INTO history (time, item, qty, action) VALUES (datetime('now'), ?, ?, ?)",
        (item, qty, "IN")
    )
    conn.commit()
    return jsonify({"status": "ok"})

# --- 出庫処理 ---
@app.route("/stock/out", methods=["POST"])
def stock_out():
    data = request.json
    item = data["item"]
    qty = data["qty"]

    conn = get_db()
    cur = conn.cursor()

    # 在庫更新（出庫なのでマイナス）
    cur.execute("UPDATE stock SET qty = qty - ? WHERE item = ?", (qty, item))

    # 履歴追加
    cur.execute(
        "INSERT INTO history (time, item, qty, action) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), item, qty, "OUT")
    )

    conn.commit()
    return jsonify({"status": "ok"})

# --- 履歴取得 ---
@app.route("/history", methods=["GET"])
def get_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM history ORDER BY time DESC")
    rows = cur.fetchall()
    return jsonify([dict(row) for row in rows])

if __name__ == "__main__":
    app.run(debug=True)
