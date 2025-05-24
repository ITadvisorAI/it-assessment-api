import os
import threading
import logging
import json
from flask import Flask, request, jsonify, send_from_directory
from generate_assessment import process_assessment
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Flask Initialization ===
app = Flask(__name__)
BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Optional Google Drive Setup ===
drive_service = None
if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
    try:
        service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("✅ Google Drive service initialized")
    except Exception as e:
        logging.warning(f"⚠️ Failed to initialize Google Drive: {e}")
else:
    logging.info("🔕 Google Drive not configured")

# === Health Check ===
@app.route("/", methods=["GET"])
def health():
    return "✅ IT Assessment API is live", 200

# === POST /start_assessment ===
@app.route("/process_assessment", methods=["POST"])
def process_assessment():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email")
        goal = data.get("goal", "N/A")
        files = data.get("files", [])
        webhook = data.get("next_action_webhook")

        logging.info(f"📥 Received session: {session_id}, email: {email}, files: {len(files)}, webhook: {webhook}")

        if not all([session_id, email, webhook, files]):
            logging.error("❌ Missing required fields")
            return jsonify({"error": "Missing required fields"}), 400

        folder = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        folder_path = os.path.join(BASE_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)
        logging.info(f"📁 Session folder created: {folder_path}")

        thread = threading.Thread(
            target=process_assessment,
            args=(session_id, email, files, webhook, folder_path),
            daemon=True
        )
        thread.start()
        logging.info("🚀 Background assessment thread started")

        return jsonify({"message": "Assessment started"}), 200

    except Exception as e:
        logging.exception("🔥 Error in /start_assessment")
        return jsonify({"error": str(e)}), 500

# === Serve Output Files ===
@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    try:
        directory = os.path.join(BASE_DIR, os.path.dirname(filename))
        file_only = os.path.basename(filename)
        logging.info(f"📤 Serving file: {filename}")
        return send_from_directory(directory, file_only)
    except Exception as e:
        logging.exception(f"❌ Error serving file: {filename}")
        return jsonify({"error": str(e)}), 500

# === Main Entry Point ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🚦 Starting IT Assessment API on port {port}...")
    app.run(host="0.0.0.0", port=port)
