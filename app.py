
import os
import threading
import logging
from flask import Flask, request, jsonify, send_from_directory
from generate_assessment import process_assessment
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Flask App Initialization ===
app = Flask(__name__)
BASE_DIR = "temp_sessions"

# === Logging Configuration ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Google Drive Setup (used in generate_assessment)
try:
    SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)
    logging.info("✅ Google Drive client initialized.")
except Exception as e:
    drive_service = None
    logging.error("❌ Google Drive not configured. Error loading service account.")
    logging.error(str(e))

# === Health Check ===
@app.route("/", methods=["GET"])
def health_check():
    return "✅ IT Assessment API is up and running", 200

# === Start Assessment Endpoint ===
@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json(force=True)
        logging.info("📥 Received POST /start_assessment")

        session_id = data.get("session_id")
        email = data.get("email")
        goal = data.get("goal", "Not Provided")
        files = data.get("files", [])
        webhook = data.get("next_action_webhook")

        logging.info(f"🧾 Session ID: {session_id}")
        logging.info(f"📧 Email: {email}")
        logging.info(f"🎯 Goal: {goal}")
        logging.info(f"📡 Webhook: {webhook}")
        logging.info(f"📂 Files received: {len(files)}")

        # Validate fields
        if not session_id or not email or not webhook or not files:
            logging.error("❌ Missing one of: session_id, email, webhook, files")
            return jsonify({"error": "Missing required fields"}), 400

        # Validate file format
        for f in files:
            if not isinstance(f, dict) or not all(k in f for k in ['file_name', 'file_url', 'type']):
                logging.error(f"❌ Malformed file entry: {f}")
                return jsonify({"error": "Malformed file entry"}), 400

        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        session_folder = os.path.join(BASE_DIR, folder_name)
        os.makedirs(session_folder, exist_ok=True)
        logging.info(f"📁 Session folder ready: {session_folder}")

        thread = threading.Thread(
            target=process_assessment,
            args=(session_id, email, files, webhook, session_folder)
        )
        thread.daemon = True
        thread.start()

        logging.info("🚀 Background assessment thread started")
        return jsonify({"message": "Assessment started"}), 200

    except Exception as e:
        logging.exception("🔥 Exception in /start_assessment")
        return jsonify({"error": str(e)}), 500

# === Serve Generated Files ===
@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    try:
        directory = os.path.join(BASE_DIR, os.path.dirname(filename))
        file_only = os.path.basename(filename)
        logging.info(f"📤 Serving file: {filename}")
        return send_from_directory(directory, file_only)
    except Exception as e:
        logging.exception(f"❌ File serve error for: {filename}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting IT Assessment Server on port {port}...")
    app.run(debug=False, host="0.0.0.0", port=port)
