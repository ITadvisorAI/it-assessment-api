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
        logging.info(f"📩 Received JSON data: {json.dumps(data, indent=2)}")

        session_id = data.get("session_id")
        if not session_id:
            raise ValueError("Missing 'session_id' in request payload")

        files = data.get("files", [])
        email = data.get("email", "")

        folder_path = os.path.join(BASE_DIR, session_id)
        os.makedirs(folder_path, exist_ok=True)
        logging.info(f"📁 Session folder created: {folder_path}")
        logging.info("🚀 Launching background thread for process_assessment...")

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
