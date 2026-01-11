"""
Google Drive API 整合模組
處理 OAuth 2.0 認證和檔案上傳功能
"""

import os
import io
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# Google Drive API 權限範圍（最小權限：只能建立檔案）
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_drive_service():
    """
    建立並返回 Google Drive API 服務實例
    處理 OAuth 2.0 認證流程：
    - 如果 token.json 存在且有效，直接使用
    - 如果 token 過期，自動刷新
    - 如果沒有 token，引導用戶授權（需要 credentials.json）

    Returns:
        service: Google Drive API 服務實例
        None: 如果認證失敗
    """
    creds = None
    token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

    # 檢查是否已有 token
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"載入 token 時發生錯誤: {e}")
            creds = None

    # 如果沒有有效的憑證，進行授權流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Token 過期，嘗試刷新
            try:
                creds.refresh(Request())
                print("Token 已刷新")
            except Exception as e:
                print(f"刷新 token 失敗: {e}")
                # 刷新失敗，需要重新授權
                creds = None

        # 需要重新授權
        if not creds:
            if not os.path.exists(credentials_path):
                print(f"錯誤：找不到 {credentials_path}")
                print("請先執行 setup_google_auth.py 完成授權")
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES)
                creds = flow.run_local_server(port=8080)
                print("授權成功")
            except Exception as e:
                print(f"OAuth 授權失敗: {e}")
                return None

        # 儲存憑證供下次使用
        try:
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"Token 已儲存到 {token_path}")
        except Exception as e:
            print(f"儲存 token 時發生錯誤: {e}")

    # 建立 Drive API 服務
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"建立 Drive 服務時發生錯誤: {e}")
        return None


def upload_image_to_drive(image_bytes, filename, folder_id=None):
    """
    上傳圖片到 Google Drive

    Args:
        image_bytes: 圖片的二進制數據（bytes）
        filename: 檔案名稱（例如："image_20240101_120000.jpg"）
        folder_id: 目標資料夾 ID（可選，None 則上傳到根目錄）

    Returns:
        dict: 成功時返回包含 file_id 和 web_view_link 的字典
              {
                  'file_id': 'xxxxx',
                  'web_view_link': 'https://drive.google.com/file/d/xxxxx/view'
              }
        None: 上傳失敗時返回 None
    """
    try:
        # 取得 Drive 服務
        service = get_drive_service()
        if not service:
            print("無法取得 Drive 服務")
            return None

        # 建立檔案 metadata
        file_metadata = {
            'name': filename,
            'mimeType': 'image/jpeg'
        }

        # 如果指定了資料夾 ID，將檔案放入該資料夾
        if folder_id:
            file_metadata['parents'] = [folder_id]

        # 建立 media upload
        media = MediaIoBaseUpload(
            io.BytesIO(image_bytes),
            mimetype='image/jpeg',
            resumable=True
        )

        # 上傳檔案
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        file_id = file.get('id')
        web_view_link = file.get('webViewLink')

        print(f"檔案上傳成功，ID: {file_id}")

        # 設定檔案權限為公開可讀（任何擁有連結的人都可以檢視）
        try:
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            print("檔案權限已設定為公開")
        except HttpError as error:
            print(f"設定檔案權限時發生錯誤: {error}")
            # 即使權限設定失敗，仍然返回檔案資訊

        return {
            'file_id': file_id,
            'web_view_link': web_view_link
        }

    except HttpError as error:
        print(f"上傳檔案時發生 HTTP 錯誤: {error}")
        return None
    except Exception as error:
        print(f"上傳檔案時發生錯誤: {error}")
        return None


def get_shareable_link(file_id):
    """
    取得檔案的可分享連結

    Args:
        file_id: Google Drive 檔案 ID

    Returns:
        str: 檔案的 web view 連結
        None: 取得失敗時返回 None
    """
    try:
        service = get_drive_service()
        if not service:
            return None

        # 取得檔案 metadata
        file = service.files().get(
            fileId=file_id,
            fields='webViewLink'
        ).execute()

        return file.get('webViewLink')

    except HttpError as error:
        print(f"取得檔案連結時發生錯誤: {error}")
        return None
