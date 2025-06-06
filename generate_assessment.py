def generate_assessment(session_id, goal, files):
    print("🧠 Inside generate_assessment()")
    print(f"🆔 Session ID: {session_id}")
    print(f"🎯 Goal: {goal}")
    print(f"📦 Total files received: {len(files)}")

    for file in files:
        print(f" - {file.get('file_name')} ({file.get('type')})")

    # Simulate report generation
    print("🛠️ Simulating DOCX and PPTX generation...")
