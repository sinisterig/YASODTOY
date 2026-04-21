import os
import time
import threading
import urllib.parse
import requests
import json
from flask import Flask, jsonify, Response
from instagrapi import Client

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.align import Align
from collections import defaultdict

console = Console()
logs_ui = defaultdict(list)
USERS = []

def ui_log(user, message):
    if user not in USERS:
        USERS.append(user)

    logs_ui[user].append(message)

    if len(logs_ui[user]) > 35:
        logs_ui[user].pop(0)

    print(message)

def build_layout():
    layout = Layout()
    layout.split_column(Layout(name="header", size=3), Layout(name="body"))

    layout["header"].update(
        Panel(
            Align.center("[bold bright_green]✦ SINISTERS | SX⁷ ✦[/bold bright_green]"),
            border_style="bright_green"
        )
    )
    return layout

def render_layout(layout):
    if USERS:
        layout["body"].split_row(*[Layout(name=u) for u in USERS])

        for user in USERS:
            content = "\n".join(logs_ui[user])
            panel = Panel(
                content,
                title=f"[bold bright_green]{user}[/bold bright_green]",
                border_style="bright_green"
            )
            layout["body"][user].update(panel)

def start_rich_ui():
    while not USERS:
        time.sleep(1)

    layout = build_layout()

    with Live(layout, console=console, refresh_per_second=5, screen=True):
        while True:
            render_layout(layout)
            time.sleep(0.2)

threading.Thread(target=start_rich_ui, daemon=True).start()

def load_lines(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def load_full_text(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Hello 👋"

SESSION_LIST = load_lines("sessions.txt")
GROUP_LIST = load_lines("groups.txt")
MESSAGE_TEXT = load_full_text("text.txt")
NC_TITLES_RAW = ",".join(load_lines("nc.txt"))

GROUP_IDS = ",".join(GROUP_LIST)

SELF_URL = os.getenv("SELF_URL", "")
SPAM_START_OFFSET = int(os.getenv("SPAM_START_OFFSET", "1"))
NC_START_OFFSET = int(os.getenv("NC_START_OFFSET", "1"))

MSG_REFRESH_DELAY = int(os.getenv("MSG_REFRESH_DELAY", "1"))
SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", "60"))
COOLDOWN_ON_ERROR = int(os.getenv("COOLDOWN_ON_ERROR", "300"))
DOC_ID = os.getenv("DOC_ID", "29088580780787855")
CSRF_TOKEN = os.getenv("CSRF_TOKEN", "")

app = Flask(__name__)

@app.route("/")
def home():
    return "alive"

@app.route('/status')
def status():
    return jsonify({user: logs_ui[user] for user in USERS})

@app.route('/logs')
def logs_route():
    output = []
    header_text = "✦  SINISTERS | SX⁷  ✦"
    output.append(header_text)
    output.append("=" * len(header_text))
    output.append("")
    for user in USERS:
        output.append(f"[ {user} ]")
        output.append("-" * (len(user) + 4))
        for line in logs_ui[user]:
            output.append(line)
        output.append("")
    return Response("\n".join(output), mimetype="text/plain")

@app.route("/dashboard")
def dashboard():
    html = """
    <html>
    <head>
        <title>SINISTERS | SX⁷</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body { background-color: #0d1117; font-family: monospace; margin: 0; padding: 20px; color: #00ff88; }
            .header { text-align: center; font-size: 28px; font-weight: bold; margin-bottom: 30px; border: 2px solid #00ff88; padding: 10px; }
            .container { display: flex; flex-direction: row; gap: 20px; align-items: flex-start; }
            .panel { flex: 1; min-width: 300px; border: 2px solid #00ff88; background-color: #111827; padding: 15px; height: 80vh; overflow-y: auto; }
            .panel-title { font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #00ff88; padding-bottom: 5px; }
            .log-line { margin-bottom: 6px; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <div class="header">✦ SINISTERS | SX⁷ ✦</div>
        <div class="container">
    """
    for user in USERS:
        html += f'<div class="panel"><div class="panel-title">{user}</div>'
        for line in logs_ui[user]:
            html += f'<div class="log-line">{line}</div>'
        html += "</div>"
    html += """
        </div>
        <script>
        function scrollPanels() {
            document.querySelectorAll('.panel').forEach(function(panel) {
                panel.scrollTop = panel.scrollHeight;
            });
        }
        window.onload = scrollPanels;
        setInterval(scrollPanels, 1500);
        </script>
    </body>
    </html>
    """
    return html

def decode_session(session):
    try:
        return urllib.parse.unquote(session)
    except:
        return session

def login_session(session_id):
    try:
        cl = Client()
        cl.login_by_sessionid(session_id)
        ui_log(cl.username, f"🍸 ID - {cl.username}")
        return cl
    except Exception as e:
        ui_log("SYSTEM", f"❌ LOGIN FAIL: {e}")
        return None

def safe_send_message(cl, gid, msg):
    try:
        cl.direct_send(msg, thread_ids=[int(gid)])
        ui_log(cl.username, f"📨 SENT - {gid}")
        return True
    except Exception:
        ui_log(cl.username, f"⚠ SEND FAIL -> {gid}")
        return False

def safe_change_title_direct(cl, gid, new_title):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-CSRFToken": CSRF_TOKEN,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/direct/t/{gid}/",
        }
        cookies = {"csrftoken": CSRF_TOKEN}

        cl.private.headers.update(headers)
        cl.private.cookies.update(cookies)

        variables = {"thread_fbid": gid, "new_title": new_title}
        payload = {"doc_id": DOC_ID, "variables": json.dumps(variables)}

        resp = cl.private.post("https://www.instagram.com/api/graphql/", data=payload, timeout=10)
        result = resp.json()

        if "errors" in result:
            ui_log(cl.username, f"❌ RENAME FAIL {gid}")
            return False

        ui_log(cl.username, f"💠 - {new_title}")
        return True

    except Exception:
        ui_log(cl.username, f"⚠ RENAME ERROR {gid}")
        return False

def spam_loop(accounts, groups):
    time.sleep(SPAM_START_OFFSET)

    n = len(accounts)
    if n == 0:
        return

    delay = 40 / n
    idx = 0

    while True:
        acc = accounts[idx]

        if acc["client"] and time.time() >= acc["cooldown_until"]:
            cl = acc["client"]

            for gid in groups:
                ok = safe_send_message(cl, gid, MESSAGE_TEXT)
                if not ok:
                    acc["cooldown_until"] = time.time() + COOLDOWN_ON_ERROR
                    break

        idx = (idx + 1) % n
        time.sleep(delay)

def parse_nc_titles():
    base = [t.strip() for t in NC_TITLES_RAW.split(",") if t.strip()]
    if not base:
        return ["SINISTERS SX⁷", "SINISTERS", "⚡ SINISTERS GOD", "💠 SAY SINSITER DADDY", "⚡ SINISTER FUCKS", "🔥 SINISTER GODX"]
    return base

def nc_loop(accounts, groups):
    titles = parse_nc_titles()
    time.sleep(NC_START_OFFSET)

    n = len(accounts)
    if n == 0:
        return

    delay = 200 / n
    acc_idx = 0
    title_idx = 0
    t_len = len(titles)

    while True:
        acc = accounts[acc_idx]

        if acc["client"]:
            cl = acc["client"]
            current_title = titles[title_idx]

            for gid in groups:
                safe_change_title_direct(cl, gid, current_title)

            title_idx = (title_idx + 1) % t_len

        acc_idx = (acc_idx + 1) % n
        time.sleep(delay)

def self_ping_loop():
    while True:
        if SELF_URL:
            try:
                requests.get(SELF_URL, timeout=10)
            except:
                pass
        time.sleep(SELF_PING_INTERVAL)

def start_bot():
    sessions = [decode_session(s) for s in SESSION_LIST if s]
    groups = [g.strip() for g in GROUP_IDS.split(",") if g.strip()]

    accounts = []
    for s in sessions:
        cl = login_session(s) if s else None
        accounts.append({"client": cl, "cooldown_until": 0})

    if not accounts:
        ui_log("SYSTEM", "❌ No sessions loaded")
        return

    threading.Thread(target=spam_loop, args=(accounts, groups), daemon=True).start()
    threading.Thread(target=nc_loop, args=(accounts, groups), daemon=True).start()
    threading.Thread(target=self_ping_loop, daemon=True).start()

def run_bot_once():
    threading.Thread(target=start_bot, daemon=True).start()

run_bot_once()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)