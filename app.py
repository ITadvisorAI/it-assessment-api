import os
import threading
import logging
import json
from flask import Flask, request, jsonify, send_from_directory
from generate_assessment import process_assessment

# Initialize Flask app
app = Flask(__name__)

# Create base session directory
BASE_DIR = "temp_sessions"
os.makedirs(BASE_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        # Parse and log incoming request data
        data = request.get_json()
        logging.info(f"📩 Received POST payload:\n{json.dumps(data, indent=2)}")

        # Defensive field extraction
        session_id = data.get("session_id")
        files = data.get("files", [])
        email = data.get("email", "")

        # Validate critical fields
        if not session_id:
            raise ValueError("Missing required field: session_id")

        # Create session folder
        folder_path = os.path.join(BASE_DIR, session_id)
        os.makedirs(folder_path, exist_ok=True)
        logging.info(f"📁 Session folder created at: {folder_path}")
        logging.info(f"📧 Email: {email} | 📂 Files: {len(files)}")

        # Launch background thread for assessment
        logging.info("🚀 Starting background thread for assessment")
        thread = threading.Thread(target=process_assessment, args=(session_id, files, email))
        thread.start()

        return jsonify({"status": "started"}), 200

    except Exception as e:
        logging.exception("❌ Failed to initiate assessment")
        return jsonify({"error": str(e)}), 500

@app.route("/files/<path:filename>", methods=["GET"])
def get_file(filename):
    try:
        session_folder = os.path.join(BASE_DIR, os.path.dirname(filename))
        return send_from_directory(session_folder, os.path.basename(filename))
    except Exception as e:
        logging.exception("❌ Failed to serve requested file")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return "✅ it-assessment-api is live"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
