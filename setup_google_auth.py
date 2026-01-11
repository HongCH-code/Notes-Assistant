"""
Google Drive OAuth 2.0 授權設定腳本
一次性執行此腳本來完成 Google Drive 授權

執行方式：
    python setup_google_auth.py

執行後會：
1. 開啟瀏覽器進行 Google 帳號登入
2. 要求授予 Google Drive 存取權限
3. 生成 token.json 檔案供 app.py 使用

注意事項：
- 執行前需要先有 credentials.json 檔案（從 Google Cloud Console 下載）
- token.json 生成後，app.py 會自動使用它來存取 Drive
- Token 會自動刷新，無需手動處理
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Google Drive API 權限範圍（最小權限：只能建立檔案）
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def main():
    """執行 OAuth 2.0 授權流程"""

    # 取得檔案路徑
    token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

    # 檢查是否已有 token
    if os.path.exists(token_path):
        print(f"⚠️  {token_path} 已存在！")
        response = input("是否要重新授權？(y/N): ")
        if response.lower() != 'y':
            print("取消授權流程")
            return

    # 檢查 credentials.json 是否存在
    if not os.path.exists(credentials_path):
        print(f"❌ 錯誤：找不到 {credentials_path}")
        print("\n請先完成以下步驟：")
        print("1. 前往 Google Cloud Console: https://console.cloud.google.com/")
        print("2. 建立或選擇專案")
        print("3. 啟用 Google Drive API")
        print("4. 建立 OAuth 2.0 憑證（應用程式類型：電腦應用程式）")
        print("5. 下載 JSON 檔案，重新命名為 'credentials.json'")
        print("6. 將 credentials.json 放到專案根目錄")
        return

    print(f"📁 使用憑證檔案: {credentials_path}")
    print(f"💾 Token 將儲存至: {token_path}")
    print("\n開始 OAuth 2.0 授權流程...")
    print("瀏覽器將自動開啟，請登入您的 Google 帳號並授權\n")

    try:
        # 啟動 OAuth 流程
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path,
            SCOPES
        )

        # 在本地伺服器上執行授權流程
        # 會自動開啟瀏覽器，授權後自動關閉
        creds = flow.run_local_server(
            port=8080,
            prompt='consent',  # 強制顯示同意畫面
            success_message='授權成功！您現在可以關閉此視窗。'
        )

        # 儲存憑證
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

        print(f"\n✅ 授權成功！")
        print(f"📝 Token 已儲存到: {token_path}")
        print("\n您現在可以：")
        print("1. 將 NOTION_IMAGE_DATABASE_ID 加入 .env 檔案")
        print("2. 啟動 Line Bot (python app.py)")
        print("3. 開始使用圖片上傳功能！")

    except Exception as e:
        print(f"\n❌ 授權失敗: {e}")
        print("\n請確認：")
        print("- credentials.json 檔案是否正確")
        print("- 網路連線是否正常")
        print("- 瀏覽器是否成功開啟")


if __name__ == '__main__':
    print("=" * 60)
    print("  Google Drive OAuth 2.0 授權設定")
    print("=" * 60)
    print()
    main()
