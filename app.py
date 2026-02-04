"""
Epstein Document Archive - Simple Web UI (Flask)
Searches text_docs.sqlite and lists image records.
"""
from flask import Flask, render_template_string, request, send_file, abort, Response
import sqlite3
import time
from pathlib import Path
import os
import base64


APP_ROOT = Path(r"C:\Users\JonathanSMcFarland\EpsteinLawyer")
TEXT_DB = APP_ROOT / "db" / "text_docs.sqlite"
IMAGES_DB = APP_ROOT / "db" / "images.sqlite"

app = Flask(__name__)

APP_USER = os.environ.get("APP_USER", "bros")
APP_PASS = os.environ.get("APP_PASS", "homies")

VIEW_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>View Document</title>
  <style>
    body { margin: 0; }
    iframe { width: 100%; height: 100vh; border: none; }
  </style>
</head>
<body>
  <iframe src="/open?path={{ path }}#page={{ page }}"></iframe>
</body>
</html>
"""

PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>Epstein Document Archive Search</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; }
    .section { margin-bottom: 2rem; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background: #f4f4f4; }
    .snippet { font-size: 0.9em; color: #333; }
  </style>
</head>
<body>
  <h1>Epstein Document Archive Search</h1>

  <div class="section">
    <h2>Search Text Documents</h2>
    <form method="get">
      <input type="text" name="q" value="{{ query }}" placeholder="Search term" size="40" />
      <button type="submit">Search</button>
    </form>
    {% if query %}
      <p>Results for: <strong>{{ query }}</strong></p>
      <table>
        <tr>
          <th>File</th>
          <th>Page</th>
          <th>Snippet</th>
        </tr>
        {% for row in results %}
          <tr>
            <td><a href="/view?path={{ row[0] }}&page={{ row[1] }}" target="_blank">{{ row[0] }}</a></td>
            <td>{{ row[1] }}</td>
            <td class="snippet">{{ row[2] }}</td>
          </tr>
        {% endfor %}
      </table>
    {% endif %}
  </div>

  <div class="section">
    <h2>Image/Scanned PDFs (latest 50)</h2>
    <table>
      <tr>
        <th>Filename</th>
        <th>Source Type</th>
        <th>Path</th>
      </tr>
      {% for row in images %}
          <tr>
            <td><a href="/view?path={{ row[2] }}" target="_blank">{{ row[0] }}</a></td>
            <td>{{ row[1] }}</td>
            <td>{{ row[2] }}</td>
          </tr>
      {% endfor %}
    </table>
  </div>
</body>
</html>
"""


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5)


def query_text(term: str):
    for attempt in range(3):
        try:
            conn = _connect_readonly(TEXT_DB)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT d.filepath, c.page_number, substr(c.extracted_text, 1, 300)
                FROM content c
                JOIN documents d ON c.document_id = d.id
                WHERE c.extracted_text LIKE ?
                LIMIT 50
                """,
                (f"%{term}%",)
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def list_images():
    for attempt in range(3):
        try:
            conn = _connect_readonly(IMAGES_DB)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT filename, source_type, filepath FROM images ORDER BY id DESC LIMIT 50"
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


@app.route("/", methods=["GET"])
def index():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    query = request.args.get("q", "").strip()
    results = query_text(query) if query else []
    images = list_images()
    return render_template_string(PAGE_TEMPLATE, query=query, results=results, images=images)


@app.route("/view", methods=["GET"])
def view_file():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    path = request.args.get("path", "")
    page = request.args.get("page", "1")
    if not path:
        abort(404)
    # Validate path in same way as /open
    file_path = Path(path)
    try:
        file_path.resolve().relative_to(APP_ROOT.resolve())
    except Exception:
        abort(403)
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    return render_template_string(VIEW_TEMPLATE, path=path, page=page)


@app.route("/open", methods=["GET"])
def open_file():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    path = request.args.get("path", "")
    if not path:
        abort(404)
    file_path = Path(path)
    # Ensure file is inside the project root
    try:
        file_path.resolve().relative_to(APP_ROOT.resolve())
    except Exception:
        abort(403)
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    return send_file(file_path, as_attachment=False)


def _auth_required():
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": "Basic realm='Epstein Archive'"}
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
