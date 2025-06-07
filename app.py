from flask import Flask, request, jsonify
import threading
from generate_assessment import generate_assessment

app = Flask(__name__)

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    data = request.get_json(force=True)
    session_id = data.get("session_id")
    email = data.get("email")
    goal = data.get("goal")
    files = data.get("files")
    next_action_webhook = data.get("next_action_webhook")

    if not session_id or not email or not files or not next_action_webhook:
        return jsonify({"error": "Missing required fields"}), 400

    def background_process():
        try:
            generate_assessment(session_id, email, goal, files, next_action_webhook)
            print(f"✅ Assessment completed for {session_id}")
        except Exception as e:
            print(f"❌ Error in background processing: {str(e)}")

    threading.Thread(target=background_process).start()
    return jsonify({"status": "Assessment started"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
