from flask import Flask, request, jsonify
import requests
import time
import threading
import random

app = Flask(__name__)

# 🧠 Caches (en mémoire)
user_id_cache = {}
user_games_cache = {}
game_passes_cache = {}

# ⚙️ Paramètres
CACHE_TTL = 300  # 5 minutes
MAX_WAIT = 10
DELAY_BETWEEN_REQUESTS = 0.5

# 🌐 Domaines alternatifs roproxy
ROPROXY_DOMAINS = [
    "https://users.roproxy.com",
    "https://users.api.roproxy.com",
    "https://users.rprxy.xyz"
]
GAMES_DOMAINS = [
    "https://games.roproxy.com",
    "https://games.api.roproxy.com",
    "https://games.rprxy.xyz"
]

# 🔍 Vérifie si un cache est encore valide
def is_cache_valid(entry):
    return time.time() - entry["timestamp"] < CACHE_TTL

# 🔒 Fonction de requête sûre (anti-429)
def safe_request(url, method="get", payload=None, timeout=6):
    time.sleep(DELAY_BETWEEN_REQUESTS)
    try:
        if method == "get":
            response = requests.get(url, timeout=timeout)
        else:
            response = requests.post(url, json=payload, timeout=timeout)

        if response.status_code == 429:
            print(f"⚠️ Trop de requêtes (429) pour {url} — pause 5s...")
            time.sleep(5)
            return None

        response.raise_for_status()
        return response
    except Exception as e:
        print(f"❌ Erreur requête : {url} — {e}")
        return None

# 🔹 Obtenir user_id à partir du username
def get_user_id(username):
    if username in user_id_cache and is_cache_valid(user_id_cache[username]):
        return user_id_cache[username]["value"]

    base = random.choice(ROPROXY_DOMAINS)
    url = f"{base}/v1/usernames/users"
    payload = {"usernames": [username]}

    response = safe_request(url, "post", payload)
    if not response:
        return None

    try:
        data = response.json()
        user_id = data["data"][0]["id"] if data.get("data") else None
        if user_id:
            user_id_cache[username] = {"value": user_id, "timestamp": time.time()}
        else:
            print(f"⚠️ Aucun user_id trouvé pour {username}")
        return user_id
    except Exception as e:
        print(f"❌ Erreur parsing get_user_id pour {username} :", e)
        return None

# 🎮 Obtenir les jeux de l'utilisateur
def get_user_games(user_id):
    if user_id in user_games_cache and is_cache_valid(user_games_cache[user_id]):
        return user_games_cache[user_id]["value"]

    base = random.choice(GAMES_DOMAINS)
    url = f"{base}/v2/users/{user_id}/games?accessFilter=2&limit=10&sortOrder=Asc"

    response = safe_request(url)
    if not response:
        return []

    try:
        data = response.json().get("data", [])
        user_games_cache[user_id] = {"value": data, "timestamp": time.time()}
        return data
    except Exception as e:
        print(f"❌ Erreur parsing get_user_games pour {user_id} :", e)
        return []

# 🎟️ Télécharger les passes d’un jeu
def fetch_game_passes(game_id):
    if game_id in game_passes_cache and is_cache_valid(game_passes_cache[game_id]):
        return game_passes_cache[game_id]["value"]

    base = random.choice(GAMES_DOMAINS)
    url = f"{base}/v1/games/{game_id}/game-passes?limit=100"

    response = safe_request(url)
    if not response:
        return []

    try:
        passes = response.json().get("data", [])
        valid_passes = [
            p for p in passes
            if isinstance(p.get("price"), (int, float)) and p["price"] > 0
        ]
        valid_passes.sort(key=lambda x: x["price"])
        game_passes_cache[game_id] = {"value": valid_passes, "timestamp": time.time()}
        print(f"✅ {len(valid_passes)} passes récupérés pour jeu {game_id}")
        return valid_passes
    except Exception as e:
        print(f"❌ Erreur parsing fetch_game_passes pour {game_id} :", e)
        return []

# 🚀 Route principale
@app.route("/api/passes")
def passes():
    username = request.args.get("username")
    userid = request.args.get("userid")
    force = request.args.get("force", "false").lower() == "true"

    if not username and not userid:
        return jsonify({"error": "Missing username or userid"}), 400

    try:
        # Récupération ID utilisateur
        if userid:
            user_id = int(userid)
        else:
            user_id = get_user_id(username)
            if not user_id:
                return jsonify({"error": "User not found"}), 404

        games = get_user_games(user_id)
        if not games:
            return jsonify([])

        result = []

        # ⚡ Ne prend que le premier jeu (évite 429)
        for game in games[:1]:
            game_id = game.get("id")
            game_name = game.get("name")
            if not game_id or not game_name:
                continue

            passes_data = fetch_game_passes(game_id)
            if not passes_data:
                continue

            result.append({
                "experienceName": game_name,
                "gameId": game_id,
                "passes": passes_data
            })

        return jsonify(result)
    except Exception as e:
        print("❌ Erreur globale :", e)
        return jsonify({"error": "Internal server error"}), 500

# 🌍 Page d’accueil
@app.route("/")
def index():
    return "<h3>🚀 Flask API active — passes Roblox</h3>"

# 🏁 Lancement sur Railway
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
