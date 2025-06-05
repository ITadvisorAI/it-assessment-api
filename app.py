
import os
from flask import Flask, request, jsonify
from generate_assessment import process_assessment

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "✅ IT Assessment API is running"

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        email = data.get("email")
        files = data.get("files", [])
        next_action_webhook = data.get("next_action_webhook")

        if not session_id or not email or not files or not next_action_webhook:
            return jsonify({"error": "Missing required fields"}), 400

        print(f"📩 Received POST payload:\n{data}")
        print(f"📁 Session folder created at: temp_sessions/{session_id}")
        print(f"📧 Email: {email} | 📂 Files: {len(files)}")
        print("🚀 Starting background thread for assessment")

        from threading import Thread
        t = Thread(target=process_assessment, args=(session_id, email, files, next_action_webhook))
        t.start()

        return jsonify({"status": "processing"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
