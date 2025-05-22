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

# === Known File Types for Logging / Validation (not enforced)
ALLOWED_TYPES = {
    "asset_inventory", "gap_working", "intake", "log", "capacity_plan",
    "compliance_report", "firewall_rules", "backup_schedule", "strategy_input", "general"
}

# === Health Check ===
@app.route('/', methods=['GET'])
def health_check():
    return "✅ IT Assessment API is up and running", 200

# === POST /start_assessment ===
@app.route('/start_assessment', methods=['POST'])
def start_assessment():
    try:
        data = request.get_json(force=True)
        logging.info("📥 Received POST /start_assessment")
        logging.debug(f"🔍 Payload: {data}")

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

        # === Basic Field Validation ===
        if not session_id or not email or not webhook or not files:
            logging.error("❌ Missing one of: session_id, email, webhook, files")
            return jsonify({"error": "Missing required fields (session_id, email, webhook, files)"}), 400

        for f in files:
            if not isinstance(f, dict) or not all(k in f for k in ['file_name', 'file_url', 'type']):
                logging.error(f"❌ Malformed file entry: {f}")
                return jsonify({"error": "Malformed file entry in 'files'"}), 400
            if f['type'] not in ALLOWED_TYPES:
                logging.warning(f"⚠️ Unrecognized file type: {f['type']} (file: {f.get('file_name')}) — will be processed as 'general'")

        # === Session folder creation ===
        folder_name = session_id if session_id.startswith("Temp_") else f"Temp_{session_id}"
        session_folder = os.path.join(BASE_DIR, folder_name)
        os.makedirs(session_folder, exist_ok=True)
        logging.info(f"📁 Session folder ready: {session_folder}")

        # === Start background processing ===
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

# === Serve Files ===
@app.route('/files/<path:filename>', methods=['GET'])
def serve_file(filename):
    try:
        directory = os.path.join(BASE_DIR, os.path.dirname(filename))
        file_only = os.path.basename(filename)
        logging.info(f"📤 Serving file: {filename}")
        return send_from_directory(directory, file_only)
    except Exception as e:
        logging.exception(f"❌ File serve error for: {filename}")
        return jsonify({"error": str(e)}), 500

# === Main Entry Point ===
if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    try:
        port = int(os.environ["PORT"])
    except KeyError:
        raise RuntimeError("❌ PORT environment variable is not set. Required by Render.")
    
    logging.info(f"🚦 Starting IT Assessment Server on port {port}...")
    app.run(debug=False, host="0.0.0.0", port=port)
