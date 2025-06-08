import os
import json
import traceback
from flask import Flask, request, jsonify
from generate_assessment import process_assessment

app = Flask(__name__)

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json(force=True)
        print("\n📥 Received trigger to start assessment")
        print(json.dumps(data, indent=2), flush=True)

        session_id = data.get("session_id")
        email = data.get("email")
        goal = data.get("goal")
        files = data.get("files", [])
        next_action_webhook = data.get("next_action_webhook")

        if not session_id or not email or not goal:
            return jsonify({"error": "Missing required fields."}), 400

        print(f"➡️ Calling process_assessment for session: {session_id}", flush=True)
        result = process_assessment(data)
        print("✅ Assessment completed. Returning result.\n", flush=True)
        return jsonify({"status": "assessment_done", "result": result}), 200

    except Exception as e:
        print("❌ Error in /start_assessment:", str(e), flush=True)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return "IT Assessment API Running", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
