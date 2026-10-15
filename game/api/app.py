import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)   # allows leaderboard.html (a different origin) to call this API

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)   # opens scores.db (creates it if missing)
    conn.row_factory = sqlite3.Row    # allows reading columns by name
    return conn

# runs when starting the api, makes a table if there isnt one
with get_connection() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL,
            level      TEXT NOT NULL,
            time_sec   REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

@app.route("/api/scores", methods=["POST"])
def save_score():
# called by the game when a game gets completed
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()[:15]
    level = str(data.get("level", "")).strip()
    try:
        time_sec = float(data.get("time"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid time"}), 400

    if not username or not level or time_sec <= 0:
        return jsonify({"error": "missing or invalid data"}), 400

    with get_connection() as conn:
# question marks used to prevent SQL injections
        conn.execute(
            "INSERT INTO scores (username, level, time_sec) VALUES (?, ?, ?)",
            (username, level, time_sec),
        )
    return jsonify({"status": "saved"}), 201

@app.route("/api/levels", methods=["GET"])
def get_levels():
#called to fill the level dropdown
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT level FROM scores ORDER BY level"
        ).fetchall()
    return jsonify([r["level"] for r in rows])

@app.route("/api/scores", methods=["GET"])
def get_scores():
# called by the webpage to get the scores
    level = request.args.get("level", "")
    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT username, MIN(time_sec) AS time_sec, level
            FROM scores
            WHERE level = ?
            GROUP BY username
            ORDER BY time_sec ASC
            LIMIT 5
            """,
            (level,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    app.run(port=5000, debug=True)