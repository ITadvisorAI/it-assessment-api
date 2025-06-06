from flask import Flask, request, jsonify
import os
from generate_assessment import generate_assessment

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ IT Assessment API is live", 200

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        print("📥 POST /start_assessment received")

        data = request.get_json(force=True)
        if not data:
            print("❌ No JSON data received")
            return jsonify({"error": "Missing JSON"}), 400

        session_id = data.get("session_id")
        email = data.get("email")
        goal = data.get("goal")
        files = data.get("files", [])
        next_action_webhook = data.get("next_action_webhook", "")

        if not session_id or not email or not goal:
            print("❌ Missing session_id, email, or goal")
            return jsonify({"error": "Missing fields"}), 400

        print(f"📦 session_id: {session_id}")
        print(f"📧 email: {email}")
        print(f"🎯 goal: {goal}")
        print(f"📁 files: {len(files)}")

        generate_assessment(session_id, goal, files)

        print("✅ generate_assessment() executed")
        return jsonify({"status": "Assessment started"}), 200

    except Exception as e:
        print("❌ Exception:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
