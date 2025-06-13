from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os

SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, file_name, session_folder_name):
    try:
        # Step 1: Locate the session folder by name
        folder_query = f"name='{session_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed = false"
        folders = drive_service.files().list(q=folder_query, fields="files(id)").execute().get("files", [])

        if not folders:
            raise Exception(f"No Google Drive folder found for session: {session_folder_name}")

        folder_id = folders[0]['id']

        # Step 2: Prepare media for upload
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if file_name.endswith(".docx") else \
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_name.endswith(".xlsx") else \
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation" if file_name.endswith(".pptx") else \
                    "application/octet-stream"

        media = MediaFileUpload(file_path, mimetype=mime_type)

        # Step 3: Upload the file
        uploaded = drive_service.files().create(
            body={
                "name": file_name,
                "parents": [folder_id]
            },
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        # Step 4: Make uploaded file publicly viewable
        drive_service.permissions().create(
            fileId=uploaded['id'],
            body={"type": "anyone", "role": "reader"},
            fields="id"
        ).execute()

        print(f"[UPLOAD] File uploaded to Google Drive: {uploaded['webViewLink']}")
        return uploaded["webViewLink"]

    except Exception as e:
        print(f"[ERROR] Failed to upload to Drive: {e}")
        raise
