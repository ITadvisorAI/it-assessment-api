import os
import threading
import logging
import json
from flask import Flask, request, jsonify, send_from_directory
from generate_assessment import process_assessment

app = Flask(__name__)
BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json()
        session_id = data["session_id"]
        files = data.get("files", [])
        email = data.get("email", "")

        logging.info(f"\U0001F4C1 Session folder created: {os.path.join(BASE_DIR, session_id)}")
        logging.info("\U0001F680 Background assessment thread started")

        thread = threading.Thread(target=process_assessment, args=(session_id, files, email))
        thread.start()

        return jsonify({"status": "started"}), 200
    except Exception as e:
        logging.exception("❌ Failed to start assessment")
        return jsonify({"error": str(e)}), 500

@app.route("/files/<path:filename>", methods=["GET"])
def get_file(filename):
    try:
        session_folder = os.path.join(BASE_DIR, os.path.dirname(filename))
        return send_from_directory(session_folder, os.path.basename(filename))
    except Exception as e:
        logging.exception("❌ Failed to serve file")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return "✅ it-assessment-api is live"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
