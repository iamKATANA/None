from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

# ─────────── APIs Roblox ───────────
USER_GAMES_API = "https://games.roblox.com/v2/users/{}/games?limit=50"
UNIVERSE_API = "https://apis.roblox.com/universes/v1/places/{}/universe"
GAMEPASSES_API = "https://apis.roblox.com/game-passes/v1/universes/{}/game-passes?limit=100&sortOrder=Asc"

# ─────────── Cache des prix ───────────
CACHE = {}   # { gamepassId: { price: int, lastUpdate: timestamp } }
TTL = 600    # 10 minutes (évite rate-limit)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.roblox.com/"
}

def scrape_price(gamepass_id):
    print(f"[SCRAPE] Price for GamePass {gamepass_id}")

    url = f"https://www.roblox.com/game-pass/{gamepass_id}"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    price_tag = soup.select_one(".text-robux-lg")

    if not price_tag:
        return None

    return int(price_tag.text.strip().replace(",", ""))

def get_price(gamepass_id):
    now = time.time()

    if gamepass_id in CACHE:
        if now - CACHE[gamepass_id]["lastUpdate"] < TTL:
            return CACHE[gamepass_id]["price"]

    price = scrape_price(gamepass_id)

    if price is not None:
        CACHE[gamepass_id] = {
            "price": price,
            "lastUpdate": now
        }

    return price

@app.route("/user/<int:user_id>/gamepasses")
def get_user_gamepasses(user_id):
    try:
        games_resp = requests.get(USER_GAMES_API.format(user_id))
        if games_resp.status_code != 200:
            return jsonify({"error": "Games API error", "details": games_resp.text}), games_resp.status_code

        games_data = games_resp.json().get("data", [])

        place_ids = [
            game.get("rootPlace", {}).get("id")
            for game in games_data if "rootPlace" in game
        ]

        place_ids = [pid for pid in place_ids if pid]

        if not place_ids:
            return jsonify({"gamepasses": [], "error": "No places found"}), 200

        universe_ids = set()
        for pid in place_ids:
            uni_resp = requests.get(UNIVERSE_API.format(pid))
            if uni_resp.status_code == 200:
                uid = uni_resp.json().get("universeId")
                if uid:
                    universe_ids.add(uid)

        if not universe_ids:
            return jsonify({"gamepasses": [], "error": "No universes found"}), 200

        all_passes = []
        for uid in universe_ids:
            gp_resp = requests.get(GAMEPASSES_API.format(uid))
            if gp_resp.status_code == 200:
                all_passes.extend(gp_resp.json().get("gamePasses", []))

        passes = {p["id"]: p for p in all_passes}.values()

        result = []
        for gp in passes:
            gp_id = gp["id"]
            price = get_price(gp_id)

            result.append({
                "id": gp_id,
                "name": gp.get("name"),
                "productId": gp.get("productId"),
                "price": price
            })

        return jsonify({
            "userId": user_id,
            "places": place_ids,
            "universes": list(universe_ids),
            "gamepasses": result
        })

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
