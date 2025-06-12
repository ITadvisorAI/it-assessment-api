import os
import json
import traceback
from flask import Flask, request, jsonify, send_from_directory
from generate_assessment import process_assessment

app = Flask(__name__)


@app.route('/files/<session_id>/<path:filename>')
def serve_generated_file(session_id, filename):
    """Serve generated files from the temp_sessions directory."""
    directory = os.path.join('temp_sessions', session_id)
    return send_from_directory(directory, filename)

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
        next_action_webhook = data.get("next_action_webhook", "")

        if not session_id or not email or not goal:
            return jsonify({"error": "Missing required fields: session_id, email, or goal"}), 400

        print(f"➡️ Calling process_assessment for session: {session_id}", flush=True)
        result = process_assessment({
            "session_id": session_id,
            "email": email,
            "goal": goal,
            "files": files,
            "next_action_webhook": next_action_webhook
        })
        print("✅ Assessment completed. Returning result.\n", flush=True)
        return jsonify({"result": result}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
