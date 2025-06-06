
import os
from flask import Flask, request, jsonify
from generate_assessment import generate_assessment

app = Flask(__name__)

@app.route("/")
def index():
    return "IT Assessment API is live"

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload received"}), 400

        session_id = data.get("session_id")
        email = data.get("email")
        goal = data.get("goal")
        files = data.get("files")

        if not session_id or not email or not goal or not files:
            return jsonify({"error": "Missing required fields"}), 400

        generate_assessment(session_id, email, goal, files)

        return jsonify({"message": "Assessment completed successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
