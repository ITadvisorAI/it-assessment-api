
import os
import threading
import logging
import json
from flask import Flask, request, jsonify
from generate_assessment import process_assessment

app = Flask(__name__)
BASE_DIR = "temp_sessions"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@app.route("/")
def home():
    return "✅ IT Assessment API is live"

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        email = data.get("email")
        files = data.get("files", [])
        webhook = data.get("next_action_webhook")

        if not session_id or not files or not email or not webhook:
            return jsonify({"error": "Missing required parameters"}), 400

        session_folder = os.path.join(BASE_DIR, session_id)
        os.makedirs(session_folder, exist_ok=True)
        logging.info(f"📁 Session folder created: {session_folder}")

        # Start background thread
        threading.Thread(
            target=process_assessment,
            args=(session_id, email, files, webhook, session_folder),
            daemon=True
        ).start()
        logging.info(f"🚀 Background assessment thread started")

        return jsonify({"message": "Assessment started"}), 200

    except Exception as e:
        logging.error(f"🔥 Failed to start assessment: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
