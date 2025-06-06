from flask import Flask, request, jsonify
import os
from generate_assessment import generate_assessment

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "IT Assessment API Running", 200

@app.route("/start_assessment", methods=["POST"])
def start_assessment():
    try:
        payload = request.get_json(force=True)
        session_id = payload.get("session_id")
        email = payload.get("email")
        goal = payload.get("goal")
        files = payload.get("files", [])

        # Convert Google Drive links into local file paths (assuming pre-downloaded)
        for f in files:
            f["local_path"] = os.path.join("temp_sessions", session_id, f["file_name"])

        print(f"▶️ Starting assessment for {session_id} - {email}")
        result = generate_assessment(session_id, files, goal)

        if result["status"] == "completed":
            return jsonify({
                "status": "completed",
                "session_id": session_id,
                "docx": result["docx"],
                "pptx": result["pptx"],
                "hw_gap": result["hw_gap"],
                "sw_gap": result["sw_gap"]
            }), 200
        else:
            return jsonify({"status": "failed", "error": result.get("error")}), 500

    except Exception as e:
        print("❌ Error in /start_assessment:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
