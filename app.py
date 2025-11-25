from flask import Flask, request, jsonify
import requests
import time
import os

app = Flask(__name__)

CACHE_TTL = 300
DELAY = 0.4

user_id_cache = {}
games_cache = {}
passes_cache = {}

def cache_valid(entry):
    return time.time() - entry["ts"] < CACHE_TTL

def safe_get(url, timeout=8):
    time.sleep(DELAY)
    try:
        r = requests.get(url, timeout=timeout)
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
# USERID → LISTE DES PLACES
# -------------------------
def get_user_places(user_id):
    if user_id in games_cache and cache_valid(games_cache[user_id]):
        return games_cache[user_id]["val"]

    url = f"https://games.roblox.com/v2/users/{user_id}/games?limit=50"

    r = safe_get(url)
    if not r:
        return []

    try:
        data = r.json().get("data", [])
        games_cache[user_id] = {"val": data, "ts": time.time()}
        return data
    except:
        return []

# -------------------------
# PLACE → GAMEPASSES (legacy)
# -------------------------
def get_place_passes(place_id):
    if place_id in passes_cache and cache_valid(passes_cache[place_id]):
        return passes_cache[place_id]["val"]

    url = f"https://games.roblox.com/v1/games/{place_id}/game-passes?limit=100"

    r = safe_get(url)
    if not r:
        return []

    try:
        raw = r.json().get("data", [])
        valid = [p for p in raw if p.get("price", 0) > 0]
        valid.sort(key=lambda x: x["price"])

        passes_cache[place_id] = {"val": valid, "ts": time.time()}
        return valid

    except Exception as e:
        print("❌ ERROR parsing passes:", e)
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

    places = get_user_places(user_id)
    if not places:
        return jsonify([])

    results = []

    for game in places:
        place_id = game.get("rootPlace", {}).get("id")
        game_name = game.get("name")

        if not place_id:
            continue

        passes = get_place_passes(place_id)
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
    return "<h1>🔥 Roblox Passes API — Legacy Passes Supported</h1>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
