from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Safe import of generate_assessment
try:
    from generate_assessment import generate_assessment
    assessment_available = True
except Exception as e:
    print("❌ ERROR IMPORTING generate_assessment:", e)
    assessment_available = False

@app.route("/")
def index():
    return "IT Assessment API is live", 200

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        email = data.get("email")
        goal = data.get("goal")
        files = data.get("files", [])
        next_action_webhook = data.get("next_action_webhook", "")

        if not session_id or not email or not goal:
            return jsonify({"error": "Missing required fields"}), 400

        print(f"[INFO] Starting assessment for session: {session_id}")
        
        if not assessment_available:
            return jsonify({"error": "Assessment engine not available. Failed to import module."}), 500
        
        generate_assessment(session_id, goal, files)

        return jsonify({"status": "Assessment started"}), 200

    except Exception as e:
        print("❌ Error in /start_assessment:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
