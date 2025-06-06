
import os
from flask import Flask, request, jsonify
from generate_assessment import generate_assessment
from threading import Thread
import requests

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
        goal = data.get("goal", "assessment")
        files = data.get("files", [])
        next_action_webhook = data.get("next_action_webhook")

        if not session_id or not email or not files:
            return jsonify({"error": "Missing required fields"}), 400

        print(f"📩 Received POST payload for session: {session_id}")
        print(f"📧 Email: {email}, 📁 Files: {len(files)}")

        def process_assessment_thread():
            print(f"🔍 Running assessment for {session_id}")
            result = generate_assessment(session_id, files, goal)
            if result and result.get("status") == "completed":
                print("✅ Assessment completed")
                if next_action_webhook:
                    try:
                        print(f"📡 Posting to next webhook: {next_action_webhook}")
                        requests.post(next_action_webhook, json={
                            "session_id": session_id,
                            "email": email,
                            "goal": goal,
                            "files": [
                                {"name": "HWGapAnalysis.xlsx", "path": result.get("hw_gap")},
                                {"name": "SWGapAnalysis.xlsx", "path": result.get("sw_gap")},
                                {"name": "Assessment_Report.docx", "path": result.get("docx")},
                                {"name": "Assessment_Deck.pptx", "path": result.get("pptx")}
                            ]
                        })
                    except Exception as e:
                        print("❌ Failed to POST to next_action_webhook:", str(e))
            else:
                print("❌ Assessment failed:", result.get("error"))

        Thread(target=process_assessment_thread).start()
        return jsonify({"status": "processing"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
