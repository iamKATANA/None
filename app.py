from flask import Flask, request, jsonify
import requests
import time
import os

app = Flask(__name__)

CACHE_TTL = 300
DELAY = 0.4

user_id_cache = {}
universes_cache = {}
passes_cache = {}

ROBLOX_API_KEY = os.getenv("ROBLOX_API_KEY")   # 🔥 récupère ta clé Open Cloud

def cache_valid(entry):
    return time.time() - entry["ts"] < CACHE_TTL

def safe_get(url, headers=None, timeout=8):
    time.sleep(DELAY)
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 429:
            time.sleep(3)
            return None
        r.raise_for_status()
        return r
    except Exception as e:
        print("❌ HTTP ERROR:", url, e)
        return None

# -------------------------
# USERNAME → USERID
# -------------------------
def get_user_id(username):
    if username in user_id_cache and cache_valid(user_id_cache[username]):
        return user_id_cache[username]["val"]

    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username]}

    try:
        r = requests.post(url, json=payload, timeout=6)
        data = r.json()
        if data.get("data"):
            uid = data["data"][0]["id"]
            user_id_cache[username] = {"val": uid, "ts": time.time()}
            return uid
    except:
        return None
    return None

# -------------------------
# USERID → UNIVERS (Open Cloud)
# -------------------------
def get_user_universes(user_id):
    if user_id in universes_cache and cache_valid(universes_cache[user_id]):
        return universes_cache[user_id]["val"]

    url = f"https://develop.roblox.com/v1/user/{user_id}/universes?isArchived=false"

    headers = {
        "x-api-key": ROBLOX_API_KEY   # 🔥 OBLIGATOIRE !!!
    }

    r = safe_get(url, headers=headers)
    if not r:
        return []

    try:
        data = r.json().get("data", [])
        universes_cache[user_id] = {"val": data, "ts": time.time()}
        return data
    except:
        return []

# -------------------------
# UNIVERSE → GAMEPASSES
# -------------------------
def fetch_gamepasses(universe_id):
    if universe_id in passes_cache and cache_valid(passes_cache[universe_id]):
        return passes_cache[universe_id]["val"]

    url = f"https://apis.roblox.com/game-passes/v1/universes/{universe_id}/game-passes?passView=Full&pageSize=100"

    headers = {
        "x-api-key": ROBLOX_API_KEY   # 🔥 obligatoire
    }

    r = safe_get(url, headers=headers)
    if not r:
        return []

    try:
        raw = r.json().get("gamePasses", []) or []
        valid = [p for p in raw if isinstance(p.get("price"), (int, float)) and p["price"] > 0]
        valid.sort(key=lambda x: x["price"])
        passes_cache[universe_id] = {"val": valid, "ts": time.time()}
        return valid
    except:
        return []

# -------------------------
# ENDPOINT PRINCIPAL
# -------------------------
@app.route("/api/passes")
def api_passes():
    username = request.args.get("username")
    userid = request.args.get("userid")

    if not username and not userid:
        return jsonify({"error": "Missing username or userid"}), 400

    if userid:
        try:
            user_id = int(userid)
        except:
            user_id = None
    else:
        user_id = get_user_id(username)

    if not user_id:
        return jsonify({"error": "User not found"}), 404

    universes = get_user_universes(user_id)
    if not universes:
        return jsonify([])

    results = []

    for uni in universes:
        universe_id = uni.get("id")
        game_name = uni.get("name", "Unknown")
        place_id = uni.get("rootPlaceId")

        if not universe_id:
            continue

        passes = fetch_gamepasses(universe_id)
        if not passes:
            continue

        results.append({
            "experienceName": game_name,
            "gameId": place_id,
            "passes": passes
        })

    return jsonify(results)

@app.route("/")
def home():
    return "<h1>🚀 Roblox Passes API — Fly.io (Hazem-style)</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
