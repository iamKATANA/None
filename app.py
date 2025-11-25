from flask import Flask, request, jsonify
import requests
import time
import random

app = Flask(__name__)

ROPROXY = [
    "https://games.roproxy.com",
    "https://games.api.roproxy.com",
    "https://games.rprxy.xyz"
]

USERS_ROPROXY = [
    "https://users.roproxy.com",
    "https://users.api.roproxy.com",
    "https://users.rprxy.xyz"
]

CACHE_TTL = 300
user_cache = {}
games_cache = {}
passes_cache = {}

def safe_get(url):
    time.sleep(0.3)
    try:
        r = requests.get(url, timeout=8)
        if r.status_code == 429:
            time.sleep(2)
            return None
        r.raise_for_status()
        return r
    except:
        return None

def get_user_id(username):
    if username in user_cache and time.time() - user_cache[username]["t"] < CACHE_TTL:
        return user_cache[username]["id"]

    base = random.choice(USERS_ROPROXY)
    url = f"{base}/v1/usernames/users"
    r = requests.post(url, json={"usernames":[username]})

    if not r:
        return None

    data = r.json().get("data")
    if not data:
        return None

    user_id = data[0]["id"]
    user_cache[username] = {"id": user_id, "t": time.time()}
    return user_id

def get_user_games(user_id):
    if user_id in games_cache and time.time() - games_cache[user_id]["t"] < CACHE_TTL:
        return games_cache[user_id]["games"]

    base = random.choice(ROPROXY)
    url = f"{base}/v2/users/{user_id}/games?accessFilter=2&limit=10&sortOrder=Asc"

    r = safe_get(url)
    if not r:
        return []

    games = r.json().get("data", [])
    games_cache[user_id] = {"games": games, "t": time.time()}
    return games

def get_game_passes(game_id):
    if game_id in passes_cache and time.time() - passes_cache[game_id]["t"] < CACHE_TTL:
        return passes_cache[game_id]["passes"]

    base = random.choice(ROPROXY)
    url = f"{base}/v1/games/{game_id}/game-passes?limit=100"
    r = safe_get(url)

    if not r:
        return []

    items = r.json().get("data", [])
    valid = []

    for p in items:
        if isinstance(p.get("price"), (int, float)) and p["price"] > 0:
            valid.append({
                "id": p["id"],
                "price": p["price"],
                "name": p.get("name")
            })

    valid.sort(key=lambda x: x["price"])
    passes_cache[game_id] = {"passes": valid, "t": time.time()}
    return valid

@app.route("/api/passes")
def api():
    username = request.args.get("username")
    userid = request.args.get("userid")

    if not username and not userid:
        return jsonify([])

    if userid:
        try:
            user_id = int(userid)
        except:
            return jsonify([])
    else:
        user_id = get_user_id(username)

    if not user_id:
        return jsonify([])

    games = get_user_games(user_id)
    if not games:
        return jsonify([])

    result = []

    for g in games[:1]:  # éviter 429
        passes = get_game_passes(g["id"])
        if passes:
            result.append({
                "experienceName": g["name"],
                "gameId": g["id"],
                "passes": passes
            })

    return jsonify(result)

@app.route("/")
def home():
    return "Roblox Passes API Online"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
