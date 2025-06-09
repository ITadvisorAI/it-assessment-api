import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")


def get_drive_service():
    """Build and return a Google Drive service instance."""
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def upload_file_to_drive(path, file_name=None, folder_id=None):
    """Upload a file to Google Drive and return a shareable link."""
    service = get_drive_service()

    metadata = {"name": file_name or os.path.basename(path)}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaFileUpload(path, resumable=False)
    file = (
        service.files()
        .create(body=metadata, media_body=media, fields="id")
        .execute()
    )
    file_id = file.get("id")

    service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}
    ).execute()

    link = (
        service.files().get(fileId=file_id, fields="webViewLink").execute().get("webViewLink")
    )
    return link
