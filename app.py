from flask import Flask, request, send_from_directory, jsonify
import os
import threading
from generate_assessment import process_assessment

app = Flask(__name__)
BASE_DIR = "temp_sessions"

@app.route('/receive_request', methods=['POST'])
def receive_request():
    try:
        data = request.get_json()

        session_id = data.get("session_id")
        email = data.get("email")
        files = data.get("files", [])
        webhook = data.get("next_action_webhook")

        print("🟢 Received request")
        print(f"Session ID: {session_id}")
        print(f"Email: {email}")
        print(f"Webhook: {webhook}")
        print(f"File count: {len(files)}")

        if not session_id or not webhook or not files:
            return jsonify({"message": "Missing required fields"}), 400

        session_folder = os.path.join(BASE_DIR, f"Temp_{session_id}")
        os.makedirs(session_folder, exist_ok=True)

        # Start async processing
        threading.Thread(
            target=process_assessment,
            args=(session_id, email, files, webhook, session_folder)
        ).start()

        return jsonify({"message": "Assessment started"}), 200

    except Exception as e:
        print(f"🔴 Error in receive_request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/files/<path:filename>', methods=['GET'])
def serve_file(filename):
    directory = os.path.join(BASE_DIR, os.path.dirname(filename))
    file_only = os.path.basename(filename)
    return send_from_directory(directory, file_only)

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
