"""
Epstein Document Archive - Simple Web UI (Flask)
Searches text_docs.sqlite and lists image records.
"""
from flask import Flask, render_template_string, request, send_file, abort, Response, redirect, jsonify
import mimetypes
import sqlite3
import time
from pathlib import Path
import os
import base64


APP_ROOT = Path(r"C:\Users\JonathanSMcFarland\EpsteinLawyer")
TEXT_DB = APP_ROOT / "db" / "text_docs.sqlite"
IMAGES_DB = APP_ROOT / "db" / "images.sqlite"
ICONS_DIR = APP_ROOT / "icons"
FAVICON_PATH = ICONS_DIR / "EpsteinPortrait.png"
HEADER_LOGO = ICONS_DIR / "EpsteinTongue.png"

app = Flask(__name__)

APP_USER = os.environ.get("APP_USER", "bros")
APP_PASS = os.environ.get("APP_PASS", "homies")

VIEW_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>View Document</title>
  <link rel="icon" type="image/png" href="/icons/EpsteinPortrait.png" />
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

IMAGE_VIEW_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>Image Viewer</title>
  <link rel="icon" type="image/png" href="/icons/EpsteinPortrait.png" />
  <style>
    body { font-family: Arial, sans-serif; margin: 1.5rem; }
    .container { max-width: 1200px; margin: 0 auto; }
    .nav { margin-bottom: 1rem; }
    .nav a { margin-right: 1rem; }
    .pager { text-align: center; margin-top: 1rem; }
    .pager a { margin: 0 0.75rem; }
    img { max-width: 100%; height: auto; border: 1px solid #ddd; }
    iframe { width: 100%; height: 85vh; border: none; }
  </style>
</head>
<body>
  <div class="container">
  <div class="nav">
    <a href="/?tab=images&image_page={{ image_page }}">Back to Images</a>
  </div>
  <h2>{{ filename }}</h2>
  <p>Type: {{ source_type }}</p>
  {% if is_pdf %}
    <iframe src="/open?path={{ filepath }}"></iframe>
  {% else %}
    <img src="/open?path={{ filepath }}" alt="{{ filename }}" />
  {% endif %}

  <div class="pager">
    {% if prev_id %}
      <a href="/image?id={{ prev_id }}&image_page={{ image_page }}">Prev</a>
    {% endif %}
    {% if next_id %}
      <a href="/image?id={{ next_id }}&image_page={{ image_page }}">Next</a>
    {% endif %}
  </div>

  <script>
    document.addEventListener('keydown', function(event) {
      if (event.key === 'ArrowRight') {
        {% if next_id %}
          window.location.href = "/image?id={{ next_id }}&image_page={{ image_page }}";
        {% endif %}
      }
      if (event.key === 'ArrowLeft') {
        {% if prev_id %}
          window.location.href = "/image?id={{ prev_id }}&image_page={{ image_page }}";
        {% endif %}
      }
    });
  </script>
  </div>
</body>
</html>
"""

PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>Epstein Document Archive Search</title>
  <link rel="icon" type="image/png" href="/icons/EpsteinPortrait.png" />
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; }
    .container { max-width: 1200px; margin: 0 auto; }
    .header-logo { display: flex; justify-content: center; margin-bottom: 1rem; }
    .header-logo img { height: 180px; width: auto; display: block; }
    h1 { text-align: center; }
    .pager { text-align: center; margin-top: 0.5rem; }
    .pager a { margin: 0 0.5rem; }
    .section { margin-bottom: 2rem; }
    .search-bar { display: inline-flex; gap: 0.5rem; align-items: center; }
    .search-input { min-width: 320px; padding: 0.5rem 0.75rem; font-size: 1rem; }
    .search-button { padding: 0.5rem 1rem; font-size: 1rem; }
    @media (max-width: 768px) {
      body { margin: 1rem; }
      .header-logo img { height: 140px; }
      .search-bar { width: 100%; justify-content: center; }
      .search-input { width: 100%; max-width: 360px; font-size: 1.1rem; padding: 0.75rem 0.9rem; }
      .search-button { font-size: 1.05rem; padding: 0.7rem 1rem; }
      table { font-size: 0.9rem; }
    }
    .tabs { margin-bottom: 1rem; text-align: center; }
    .tab { display: inline-block; margin-right: 0.75rem; padding: 0.5rem 1rem; border: 1px solid #ccc; border-radius: 4px; text-decoration: none; color: #333; }
    .tab.active { background: #333; color: #fff; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background: #f4f4f4; }
    .snippet { font-size: 0.9em; color: #333; }
  </style>
</head>
<body>
  <div class="container">
  <a class="header-logo" href="/">
    <img src="/icons/EpsteinTongue.png" alt="Epstein Archive" />
  </a>
  <h1>Epstein Document Archive Search</h1>

  <div class="tabs">
    <a class="tab {% if tab == 'text' %}active{% endif %}" href="/?tab=text">Text</a>
    <a class="tab {% if tab == 'images' %}active{% endif %}" href="/?tab=images">Images</a>
  </div>

  {% if tab == 'text' %}
  <div class="section">
    <h2>Search Text Documents</h2>
    <form method="get" style="text-align: center;">
      <div class="search-bar">
        <input class="search-input" type="text" name="q" value="{{ query }}" placeholder="Search term" />
        <button class="search-button" type="submit">Search</button>
      </div>
    </form>
    {% if query %}
      <p>Results for: <strong>{{ query }}</strong></p>
    {% endif %}
    <table>
      <tr>
        <th>File</th>
        <th>Page</th>
        <th>Snippet</th>
      </tr>
      {% for row in results %}
        <tr>
          <td><a href="/view?id={{ row[0] }}&page={{ row[2] }}" target="_blank">{{ row[1] }}</a></td>
          <td>{{ row[2] }}</td>
          <td class="snippet">{{ row[3] }}</td>
        </tr>
      {% endfor %}
    </table>
    <p>Page {{ page }} of {{ total_pages }} ({{ total_results }} results)</p>
    <div class="pager">
      {% if page > 1 %}
        <a href="/?tab=text&q={{ query }}&page={{ page - 1 }}">Prev</a>
      {% endif %}
      {% if page < total_pages %}
        <a href="/?tab=text&q={{ query }}&page={{ page + 1 }}">Next</a>
      {% endif %}
    </div>
    <form method="get" style="margin-top: 0.75rem; text-align: center;">
      <input type="hidden" name="tab" value="text" />
      <input type="hidden" name="q" value="{{ query }}" />
      <label>Go to page:
        <input type="number" name="page" min="1" max="{{ total_pages }}" value="{{ page }}" style="width: 6rem;" />
      </label>
      <button type="submit">Go</button>
    </form>
    </div>

  {% elif tab == 'images' %}
  <div class="section">
    <h2>Image/Scanned PDFs</h2>
    <table>
      <tr>
        <th>Filename</th>
        <th>Source Type</th>
        <th>Path</th>
      </tr>
      {% for row in images %}
          <tr>
            <td><a href="/image?id={{ row[0] }}&image_page={{ image_page }}" target="_blank">{{ row[1] }}</a></td>
            <td>{{ row[2] }}</td>
            <td>{{ row[3] }}</td>
          </tr>
      {% endfor %}
    </table>
    <p>Page {{ image_page }} of {{ image_total_pages }} ({{ image_total_results }} images)</p>
    <div class="pager">
      {% if image_page > 1 %}
        <a href="/?tab=images&image_page={{ image_page - 1 }}">Prev</a>
      {% endif %}
      {% if image_page < image_total_pages %}
        <a href="/?tab=images&image_page={{ image_page + 1 }}">Next</a>
      {% endif %}
    </div>
    <form method="get" style="margin-top: 0.75rem; text-align: center;">
      <input type="hidden" name="tab" value="images" />
      <label>Go to page:
        <input type="number" name="image_page" min="1" max="{{ image_total_pages }}" value="{{ image_page }}" style="width: 6rem;" />
      </label>
      <button type="submit">Go</button>
    </form>
  </div>
  {% endif %}
  </div>
</body>
</html>
"""


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=5)


def query_text(term: str, limit: int, offset: int):
    for attempt in range(3):
        try:
            conn = _connect_readonly(TEXT_DB)
            cursor = conn.cursor()
            if term:
                cursor.execute(
                    """
                    SELECT d.filepath, c.page_number, substr(c.extracted_text, 1, 300)
                    FROM content c
                    JOIN documents d ON c.document_id = d.id
                    WHERE c.extracted_text LIKE ?
                    LIMIT ? OFFSET ?
                    """,
                    (f"%{term}%", limit, offset)
                )
            else:
                cursor.execute(
                    """
                    SELECT d.filepath, c.page_number, substr(c.extracted_text, 1, 300)
                    FROM content c
                    JOIN documents d ON c.document_id = d.id
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def query_text_with_ids(term: str, limit: int, offset: int):
    for attempt in range(3):
        try:
            conn = _connect_readonly(TEXT_DB)
            cursor = conn.cursor()
            if term:
                cursor.execute(
                    """
                    SELECT d.id, d.filepath, c.page_number, substr(c.extracted_text, 1, 300)
                    FROM content c
                    JOIN documents d ON c.document_id = d.id
                    WHERE c.extracted_text LIKE ?
                    LIMIT ? OFFSET ?
                    """,
                    (f"%{term}%", limit, offset)
                )
            else:
                cursor.execute(
                    """
                    SELECT d.id, d.filepath, c.page_number, substr(c.extracted_text, 1, 300)
                    FROM content c
                    JOIN documents d ON c.document_id = d.id
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def count_docs() -> int:
    for attempt in range(3):
        try:
            conn = _connect_readonly(TEXT_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents")
            total = cursor.fetchone()[0]
            conn.close()
            return total
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def count_pages() -> int:
    for attempt in range(3):
        try:
            conn = _connect_readonly(TEXT_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM content")
            total = cursor.fetchone()[0]
            conn.close()
            return total
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def get_document_text(doc_id: int):
    conn = _connect_readonly(TEXT_DB)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT page_number, extracted_text FROM content WHERE document_id = ? ORDER BY page_number",
        (doc_id,)
    )
    pages = [
        {"page": row[0], "text": row[1]}
        for row in cursor.fetchall()
    ]
    cursor.execute("SELECT filepath FROM documents WHERE id = ?", (doc_id,))
    doc_row = cursor.fetchone()
    conn.close()
    filepath = doc_row[0] if doc_row else None
    return filepath, pages


def count_text(term: str) -> int:
    for attempt in range(3):
        try:
            conn = _connect_readonly(TEXT_DB)
            cursor = conn.cursor()
            if term:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM content c
                    WHERE c.extracted_text LIKE ?
                    """,
                    (f"%{term}%",)
                )
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM content c
                    """
                )
            total = cursor.fetchone()[0]
            conn.close()
            return total
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def list_images(limit: int, offset: int):
    for attempt in range(3):
        try:
            conn = _connect_readonly(IMAGES_DB)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, filename, source_type, filepath
                FROM images
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def count_images() -> int:
    for attempt in range(3):
        try:
            conn = _connect_readonly(IMAGES_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM images")
            total = cursor.fetchone()[0]
            conn.close()
            return total
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def get_image_record(image_id: int):
    conn = _connect_readonly(IMAGES_DB)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, filename, filepath, source_type FROM images WHERE id = ?",
        (image_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def get_prev_next_image_ids(image_id: int):
    conn = _connect_readonly(IMAGES_DB)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM images WHERE id > ? ORDER BY id ASC LIMIT 1",
        (image_id,)
    )
    prev_row = cursor.fetchone()
    cursor.execute(
        "SELECT id FROM images WHERE id < ? ORDER BY id DESC LIMIT 1",
        (image_id,)
    )
    next_row = cursor.fetchone()
    conn.close()
    prev_id = prev_row[0] if prev_row else None
    next_id = next_row[0] if next_row else None
    return prev_id, next_id


@app.route("/", methods=["GET"])
def index():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    tab = request.args.get("tab", "text").strip().lower()
    if tab not in {"images", "text"}:
        tab = "images"
    query = request.args.get("q", "").strip()
    page = max(int(request.args.get("page", "1")), 1)
    per_page = 50
    image_page = max(int(request.args.get("image_page", "1")), 1)
    image_per_page = 50
    total_results = 0
    total_pages = 1
    results = []
    image_total_results = 0
    image_total_pages = 1
    images = []

    if tab == "text":
        total_results = count_text(query)
        total_pages = max((total_results + per_page - 1) // per_page, 1)
        offset = (page - 1) * per_page
        results = query_text_with_ids(query, per_page, offset)
    else:
        image_total_results = count_images()
        image_total_pages = max((image_total_results + image_per_page - 1) // image_per_page, 1)
        image_offset = (image_page - 1) * image_per_page
        images = list_images(image_per_page, image_offset)
    return render_template_string(
        PAGE_TEMPLATE,
        tab=tab,
        query=query,
        results=results,
        images=images,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
        image_page=image_page,
        image_total_pages=image_total_pages,
        image_total_results=image_total_results,
    )


@app.route("/image", methods=["GET"])
def view_image():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    image_id = request.args.get("id")
    image_page = request.args.get("image_page", "1")
    if not image_id or not image_id.isdigit():
        abort(404)
    record = get_image_record(int(image_id))
    if not record:
        abort(404)
    _, filename, filepath, source_type = record
    prev_id, next_id = get_prev_next_image_ids(int(image_id))
    is_pdf = Path(filepath).suffix.lower() == ".pdf"
    return render_template_string(
        IMAGE_VIEW_TEMPLATE,
        filename=filename,
        filepath=filepath,
        source_type=source_type,
        is_pdf=is_pdf,
        prev_id=prev_id,
        next_id=next_id,
        image_page=image_page,
    )


@app.route("/view", methods=["GET"])
def view_file():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    doc_id = request.args.get("id", "").strip()
    path = request.args.get("path", "")
    page = request.args.get("page", "1")
    if not path and not doc_id:
        abort(404)
    if not path and doc_id.isdigit():
        conn = _connect_readonly(TEXT_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT filepath FROM documents WHERE id = ?", (int(doc_id),))
        row = cursor.fetchone()
        conn.close()
        if not row:
            abort(404)
        path = row[0]
    file_path = Path(path)
    try:
        file_path.resolve().relative_to(APP_ROOT.resolve())
    except Exception:
        abort(403)
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    user_agent = request.headers.get("User-Agent", "").lower()
    if any(token in user_agent for token in ["iphone", "ipad", "android", "mobile"]):
        return redirect(f"/open?path={path}")
    return render_template_string(VIEW_TEMPLATE, path=path, page=page)


@app.route("/api/search", methods=["GET"])
def api_search():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    query = request.args.get("q", "").strip()
    page = max(int(request.args.get("page", "1")), 1)
    per_page = min(max(int(request.args.get("per_page", "50")), 1), 200)
    total_results = count_text(query)
    offset = (page - 1) * per_page
    rows = query_text_with_ids(query, per_page, offset)
    results = [
        {
            "doc_id": row[0],
            "filepath": row[1],
            "page": row[2],
            "snippet": row[3]
        }
        for row in rows
    ]
    return jsonify({
        "query": query,
        "total_results": total_results,
        "page": page,
        "per_page": per_page,
        "results": results
    })


@app.route("/api/search/batch", methods=["POST"])
def api_search_batch():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    payload = request.get_json(silent=True) or {}
    names = payload.get("names", [])
    batch_results = {}
    for name in names:
        rows = query_text_with_ids(name, 50, 0)
        batch_results[name] = [
            {
                "doc_id": row[0],
                "filepath": row[1],
                "page": row[2],
                "snippet": row[3]
            }
            for row in rows
        ]
    return jsonify({"results": batch_results})


@app.route("/api/stats", methods=["GET"])
def api_stats():
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    return jsonify({
        "total_docs": count_docs(),
        "total_pages": count_pages(),
        "total_images": count_images()
    })


@app.route("/api/text/<int:doc_id>", methods=["GET"])
def api_text(doc_id: int):
    auth = request.authorization
    if not auth or not (auth.username == APP_USER and auth.password == APP_PASS):
        return _auth_required()
    filepath, pages = get_document_text(doc_id)
    if not filepath:
        abort(404)
    return jsonify({
        "doc_id": doc_id,
        "filepath": filepath,
        "pages": pages
    })


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
    mimetype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = send_file(file_path, as_attachment=False, mimetype=mimetype)
    if file_path.suffix.lower() == ".pdf":
        response.headers["Content-Disposition"] = f"inline; filename=\"{file_path.name}\""
    return response


def _auth_required():
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": "Basic realm='Epstein Archive'"}
    )


@app.route("/icons/<path:filename>", methods=["GET"])
def icon_file(filename: str):
    icon_path = ICONS_DIR / filename
    if not icon_path.exists():
        abort(404)
    return send_file(icon_path)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
