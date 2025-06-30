import os
import re
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Path to your service account JSON key
SERVICE_ACCOUNT_FILE = "/etc/secrets/service_account.json"

# Authenticate and construct the Drive API client if credentials exist
if os.path.exists(SERVICE_ACCOUNT_FILE):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build('drive', 'v3', credentials=creds)
else:
    creds = None
    drive_service = None

def upload_to_drive(file_path: str, file_name: str, folder_identifier: str) -> str:
    """
    Upload a local file to Google Drive, using either a folder name or a folder ID.

    :param file_path: Local path to the file
    :param file_name: Name to assign to the file in Drive
    :param folder_identifier: Drive folder ID or folder name
    :return: webViewLink for the uploaded file
    """
    if drive_service is None:
        print("[WARN] Drive service not configured; returning local path", flush=True)
        return file_path

    # Determine if the identifier is a Drive folder ID (alphanumeric, "-" or "_", ~20+ chars)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", folder_identifier):
        folder_id = folder_identifier
    else:
        # Look up a folder by name
        query = (
            f"name='{folder_identifier}' and mimeType='application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        resp = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = resp.get('files', [])
        if files:
            folder_id = files[0]['id']
        else:
            # Create the folder if not found
            metadata = {
                'name': folder_identifier,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            created = drive_service.files().create(body=metadata, fields="id").execute()
            folder_id = created.get('id')

    # Upload the file into the resolved folder
    media = MediaFileUpload(file_path, resumable=True)
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    # Make the file publicly readable
    drive_service.permissions().create(
        fileId=uploaded['id'],
        body={'type': 'anyone', 'role': 'reader'},
        fields='id'
    ).execute()

    print(f"[UPLOAD] '{file_name}' uploaded to folder '{folder_identifier}' (ID: {folder_id})")
    return uploaded.get('webViewLink', '')
