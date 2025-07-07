from flask import Flask, request, jsonify
import requests
import time

app = Flask(__name__)

# 🧠 Caches simples (en mémoire)
user_id_cache = {}
user_games_cache = {}
game_passes_cache = {}

# ⏳ Durée max du cache (en secondes)
CACHE_TTL = 60  # 1 minute

def is_cache_valid(entry):
    return time.time() - entry["timestamp"] < CACHE_TTL

# 🔍 Obtenir l’ID du joueur depuis le username
def get_user_id(username):
    if username in user_id_cache and is_cache_valid(user_id_cache[username]):
        return user_id_cache[username]["value"]

    url = "https://users.roproxy.com/v1/usernames/users"
    payload = {"usernames": [username]}
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        user_id = data["data"][0]["id"] if data.get("data") else None
        if user_id:
            user_id_cache[username] = {"value": user_id, "timestamp": time.time()}
        return user_id
    except Exception as e:
        print("❌ Erreur get_user_id :", e)
        return None

# 🎮 Obtenir la liste des expériences du joueur
def get_user_games(user_id):
    if user_id in user_games_cache and is_cache_valid(user_games_cache[user_id]):
        return user_games_cache[user_id]["value"]

    url = f"https://games.roproxy.com/v2/users/{user_id}/games?accessFilter=2&limit=50&sortOrder=Asc"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json().get("data", [])
        user_games_cache[user_id] = {"value": data, "timestamp": time.time()}
        return data
    except Exception as e:
        print("❌ Erreur get_user_games :", e)
        return []

# 🎟️ Obtenir les Game Pass filtrés (avec prix > 0)
def get_game_passes(game_id):
    if game_id in game_passes_cache and is_cache_valid(game_passes_cache[game_id]):
        return game_passes_cache[game_id]["value"]

    url = f"https://games.roproxy.com/v1/games/{game_id}/game-passes?limit=100"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        passes = response.json().get("data", [])

        valid_passes = [
            p for p in passes
            if isinstance(p.get("price"), (int, float)) and p["price"] > 0
        ]
        valid_passes.sort(key=lambda x: x["price"])
        game_passes_cache[game_id] = {"value": valid_passes, "timestamp": time.time()}
        return valid_passes
    except Exception as e:
        print(f"❌ Erreur get_game_passes pour {game_id} :", e)
        return []

# 🚀 Route principale de l’API
@app.route("/api/passes")
def passes():
    username = request.args.get("username")
    userid = request.args.get("userid")

    if not username and not userid:
        return jsonify({"error": "Missing username or userid"}), 400

    try:
        if userid:
            user_id = int(userid)
        else:
            user_id = get_user_id(username)
            if not user_id:
                return jsonify({"error": "User not found"}), 404

        result = []
        for game in get_user_games(user_id):
            game_id = game.get("id")
            game_name = game.get("name")
            if not game_id or not game_name:
                continue

            passes = get_game_passes(game_id)
            if not passes:
                continue

            result.append({
                "experienceName": game_name,
                "gameId": game_id,
                "passes": passes
            })

        return jsonify(result)
    except Exception as e:
        print("❌ Erreur globale :", e)
        return jsonify({"error": "Erreur serveur. Veuillez réessayer."}), 500

# Page d’accueil simple
@app.route("/")
def index():
    return "<span style='font-family:Gotham, sans-serif;'>🚀 Flask API en ligne !</span>"

# Lancer avec Gunicorn sur Railway (port dynamique)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
