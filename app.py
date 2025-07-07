from flask import Flask, request, jsonify
import requests
import time
import threading

app = Flask(__name__)

# 🧠 Caches simples (en mémoire)
user_id_cache = {}
user_games_cache = {}
game_passes_cache = {}  # { game_id: { value: [...], timestamp: float } }

# ⏳ Paramètres
CACHE_TTL = 60  # 1 minute
MAX_WAIT = 10   # Max 10s d’attente active si données pas prêtes

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

# 🎮 Obtenir les expériences de l’utilisateur
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

# 🎟️ Télécharge et met en cache les Game Pass (thread séparé)
def fetch_game_passes_async(game_id):
    if game_id in game_passes_cache and is_cache_valid(game_passes_cache[game_id]):
        return

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
    except Exception as e:
        print(f"❌ Erreur fetch_game_passes pour {game_id} :", e)

# 🔁 Attente active jusqu’à ce que les Game Pass soient présents
def wait_for_game_passes(game_id):
    if game_id not in game_passes_cache:
        threading.Thread(target=fetch_game_passes_async, args=(game_id,)).start()

    start = time.time()
    while time.time() - start < MAX_WAIT:
        if game_id in game_passes_cache:
            return game_passes_cache[game_id]["value"]
        time.sleep(0.2)  # attend 200ms

    return []  # timeout

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

            passes = wait_for_game_passes(game_id)
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
