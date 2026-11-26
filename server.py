"""
CNE RNG — Backend with Account-based Cloud Persistence
Run: uvicorn server:app --reload --port 8000
"""
import hashlib, secrets, sqlite3, os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB = os.path.join(os.path.dirname(__file__), "cne.db")
app = FastAPI(title="CNE RNG API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            pfp TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS game_states (
            user_id INTEGER PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS live_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            character TEXT NOT NULL,
            tier TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Migration for pre-existing databases that did not have pfp column
    try:
        c.execute("ALTER TABLE users ADD COLUMN pfp TEXT DEFAULT ''")
        c.commit()
    except Exception:
        pass
    c.close()

init()

def hash_pw(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()

def make_token() -> str:
    return secrets.token_hex(32)

def get_user_id(token: str) -> int:
    c = db()
    row = c.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token=?", (token,)
    ).fetchone()
    c.close()
    if not row:
        raise HTTPException(401, "Invalid session")
    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        raise HTTPException(401, "Session expired")
    return row["user_id"]

def auth_header(authorization: str = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    return get_user_id(authorization.split(" ", 1)[1])

TIER_RANK = {
    "COMMON": 1, "RARE": 2, "EPIC": 3, "LEGENDARY": 4, 
    "MYTHIC": 5, "CELESTIAL": 6, "SECRET": 7, "LEGEND": 8, "TRANSCENDENT": 9
}

class AuthBody(BaseModel):
    username: str
    password: str

class StateBody(BaseModel):
    state_json: str

class ProfileBody(BaseModel):
    username: str
    pfp: str = ""

class FeedPost(BaseModel):
    character: str
    tier: str

@app.post("/api/auth/register")
def register(body: AuthBody):
    u = body.username.strip()
    if len(u) < 3:
        raise HTTPException(400, "Username too short (min 3)")
    if len(body.password) < 6:
        raise HTTPException(400, "Password too short (min 6)")
    salt = secrets.token_hex(16)
    pw_hash = hash_pw(body.password, salt)
    c = db()
    try:
        c.execute("INSERT INTO users (username,salt,pw_hash) VALUES (?,?,?)", (u, salt, pw_hash))
        c.commit()
        user_id = c.execute("SELECT id FROM users WHERE username=?", (u,)).fetchone()["id"]
    except sqlite3.IntegrityError:
        c.close(); raise HTTPException(409, "Username already taken")
    token = make_token()
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    c.execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)", (token, user_id, expires))
    c.commit(); c.close()
    return {"token": token, "username": u, "pfp": ""}

@app.post("/api/auth/login")
def login(body: AuthBody):
    u = body.username.strip()
    c = db()
    row = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    if not row or hash_pw(body.password, row["salt"]) != row["pw_hash"]:
        c.close(); raise HTTPException(401, "Invalid credentials")
    token = make_token()
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    c.execute("INSERT OR REPLACE INTO sessions (token,user_id,expires_at) VALUES (?,?,?)",
              (token, row["id"], expires))
    c.commit(); c.close()
    pfp_val = ""
    try:
        pfp_val = row["pfp"] or ""
    except Exception:
        pfp_val = ""
    return {"token": token, "username": u, "pfp": pfp_val}

@app.post("/api/profile")
def update_profile(body: ProfileBody, authorization: str = Header(None)):
    uid = auth_header(authorization)
    c = db()
    new_name = body.username.strip()
    if len(new_name) < 3:
        raise HTTPException(400, "Username too short (min 3)")
    try:
        c.execute("UPDATE users SET username=?, pfp=? WHERE id=?", (new_name, body.pfp.strip(), uid))
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); raise HTTPException(409, "Username already taken")
    c.close()
    return {"ok": True, "username": new_name, "pfp": body.pfp.strip()}

@app.get("/api/state")
def load_state(authorization: str = Header(None)):
    uid = auth_header(authorization)
    c = db()
    row = c.execute("SELECT state_json FROM game_states WHERE user_id=?", (uid,)).fetchone()
    user = c.execute("SELECT username, pfp FROM users WHERE id=?", (uid,)).fetchone()
    c.close()
    pfp_val = ""
    try:
        pfp_val = user["pfp"] or ""
    except Exception:
        pfp_val = ""
    if not row:
        return {"state": None, "username": user["username"], "pfp": pfp_val}
    import json
    return {"state": json.loads(row["state_json"]), "username": user["username"], "pfp": pfp_val}

@app.post("/api/state")
def save_state(body: StateBody, authorization: str = Header(None)):
    uid = auth_header(authorization)
    now = datetime.utcnow().isoformat()
    c = db()
    c.execute("""INSERT INTO game_states (user_id,state_json,updated_at) VALUES (?,?,?)
                 ON CONFLICT(user_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at""",
              (uid, body.state_json, now))
    c.commit(); c.close()
    return {"ok": True}

@app.post("/api/feed")
def post_feed(body: FeedPost, authorization: str = Header(None)):
    uid = auth_header(authorization)
    c = db()
    user = c.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
    if user:
        c.execute("INSERT INTO live_feed (username, character, tier) VALUES (?,?,?)",
                  (user["username"], body.character, body.tier))
        c.execute("DELETE FROM live_feed WHERE id NOT IN (SELECT id FROM live_feed ORDER BY id DESC LIMIT 50)")
        c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/feed")
def get_feed():
    c = db()
    rows = c.execute("SELECT username, character, tier, timestamp FROM live_feed ORDER BY id DESC LIMIT 15").fetchall()
    c.close()
    return [dict(r) for r in rows]

@app.get("/api/leaderboard")
def leaderboard():
    import json
    c = db()
    rows = c.execute("""
        SELECT u.username, u.pfp, gs.state_json
        FROM users u JOIN game_states gs ON u.id=gs.user_id
    """).fetchall()
    c.close()
    result = []
    for row in rows:
        try:
            s = json.loads(row["state_json"])
            inv = s.get("inventory", {})
            unique = sum(1 for v in inv.values() if v > 0)
            total = sum(inv.values())
            coins = s.get("coins", 0)
            best = s.get("best_pull_tier", "COMMON")
            pfp_val = ""
            try:
                pfp_val = row["pfp"] or ""
            except Exception:
                pfp_val = ""
            result.append({
                "username": row["username"],
                "pfp": pfp_val,
                "unique": unique,
                "total_rolls": total,
                "best_pull_tier": best,
                "coins": coins,
                "title": s.get("equipped_title", "Novice"),
                "title_class": s.get("equipped_title_class", "title-novice"),
                "equipped_nameplate": s.get("equipped_nameplate", ""),
                "equipped_wrap": s.get("equipped_wrap", "wrap-none"),
                "equipped_anim": s.get("equipped_anim", "anim-none"),
                "equipped_font": s.get("equipped_font", "font-outfit"),
                "equipped_border": s.get("equipped_border", "border-none"),
                "equipped_theme": s.get("equipped_theme", "theme-default"),
                "inventory": inv
            })
        except Exception:
            continue
    result.sort(key=lambda x: (-x["unique"], x["total_rolls"]))
    for i, r in enumerate(result):
        r["rank"] = i + 1
    return result[:50]

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

nameplates_dir = os.path.join(os.path.dirname(__file__), "nameplates")
if os.path.isdir(nameplates_dir):
    app.mount("/nameplates", StaticFiles(directory=nameplates_dir), name="nameplates")

@app.get("/nameplates_data.js")
def get_nameplates_data():
    p = os.path.join(os.path.dirname(__file__), "nameplates_data.js")
    if os.path.exists(p):
        return FileResponse(p, media_type="application/javascript")
    raise HTTPException(404, "File not found")

@app.get("/")
def root():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "CNE RNG Backend Active"}

@app.get("/index.html")
def root_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
