from flask import Flask, request, send_from_directory, jsonify
import os
import threading
import logging
from generate_assessment import process_assessment

# === Flask App Initialization ===
app = Flask(__name__)
BASE_DIR = "temp_sessions"

# === Logging Configuration ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Allowed File Types ===
ALLOWED_TYPES = {"asset_inventory", "gap_working", "intake", "log"}

# === Health Check Route ===
@app.route('/', methods=['GET'])
def health_check():
    return "✅ IT Assessment API is up and running", 200

# === Receive POST Request from GPT1 ===
@app.route('/receive_request', methods=['POST'])
def receive_request():
    try:
        data = request.get_json(force=True)
        logging.info("📥 Received POST /receive_request with payload")

        session_id = data.get("session_id")
        email = data.get("email")
        files = data.get("files", [])
        webhook = data.get("next_action_webhook")

        logging.info(f"🧾 Session ID: {session_id}")
        logging.info(f"📧 Email: {email}")
        logging.info(f"📡 Webhook: {webhook}")
        logging.info(f"📂 Files received: {len(files)}")

        # === Validate Required Fields ===
        if not session_id or not webhook or not files:
            logging.error("❌ Missing required fields in request")
            return jsonify({"message": "Missing required fields"}), 400

        # === Validate Each File Entry ===
        for f in files:
            if not all(k in f for k in ['file_name', 'file_url', 'type']):
                logging.error("❌ Malformed file entry in 'files' list")
                return jsonify({"message": "Malformed file entry"}), 400
            if f['type'] not in ALLOWED_TYPES:
                logging.warning(f"⚠️ Unrecognized file type: {f['type']} (name: {f.get('file_name')})")

        # === Normalize Session Folder Name ===
        if session_id.startswith("Temp_"):
            folder_name = session_id
        else:
            folder_name = f"Temp_{session_id}"

        session_folder = os.path.join(BASE_DIR, folder_name)
        os.makedirs(session_folder, exist_ok=True)
        logging.info(f"📁 Created/verified session folder at: {session_folder}")

        # === Run Assessment in Background Thread ===
        thread = threading.Thread(
            target=process_assessment,
            args=(session_id, email, files, webhook, session_folder)
        )
        thread.daemon = True
        thread.start()
        logging.info("🚀 Background thread for assessment started successfully")

        return jsonify({"message": "Assessment started"}), 200

    except Exception as e:
        logging.exception("🔥 Exception occurred in /receive_request")
        return jsonify({"error": str(e)}), 500

# === Serve Generated Files via /files/... ===
@app.route('/files/<path:filename>', methods=['GET'])
def serve_file(filename):
    try:
        directory = os.path.join(BASE_DIR, os.path.dirname(filename))
        file_only = os.path.basename(filename)
        logging.info(f"📤 Serving file: {filename}")
        return send_from_directory(directory, file_only)
    except Exception as e:
        logging.exception(f"❌ Failed to serve file: {filename}")
        return jsonify({"error": str(e)}), 500

# === Entry Point ===
if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    logging.info("🚦 IT Assessment Flask server starting...")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
