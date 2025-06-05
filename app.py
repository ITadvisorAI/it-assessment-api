from flask import Flask, request, jsonify
import threading
import logging
from generate_assessment import process_assessment

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

@app.route("/", methods=["GET"])
def index():
    return "✅ IT Assessment API is live"

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    data = request.get_json()
    session_id = data.get("session_id")
    email = data.get("email")
    goal = data.get("goal")
    files = data.get("files", [])
    next_action_webhook = data.get("next_action_webhook")

    logging.info("📩 Received POST payload:\n%s", data)
    logging.info("📁 Session folder created at: temp_sessions/%s", session_id)
    logging.info("📧 Email: %s | 📂 Files: %d", email, len(files))
    logging.info("🚀 Starting background thread for assessment")

    thread = threading.Thread(
        target=process_assessment,
        args=(session_id, email, files, next_action_webhook)
    )
    thread.start()

    return jsonify({"status": "processing started"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
