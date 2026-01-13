# LINE Notes Assistant Bot

一個智能筆記助手 LINE Bot，支援語音轉文字、圖片分析、社群媒體爬文、網頁摘要等功能，並自動整理儲存到 Notion。

## 主要功能

### 📝 語音筆記
- 傳送語音訊息自動轉換為文字（使用 OpenAI Whisper）
- AI 自動生成標籤分類
- 儲存到 Notion 語音筆記資料庫
- 記錄語音時長

### 📄 文字摘要
- 使用 `/a` 指令加上文字內容
- AI 自動生成摘要和分類
- 儲存到 Notion 摘要筆記資料庫
- 來源標記為「文字」

### 🖼️ 圖片分析
- 傳送圖片自動上傳到 Google Drive
- AI 視覺分析圖片內容並生成描述
- 自動生成圖片標籤
- 儲存圖片資訊到 Notion 圖片資料庫

### 🌐 網頁爬取與摘要
- 貼上任何網址自動爬取內容
- AI 生成摘要和分類
- 儲存到 Notion 摘要筆記資料庫
- 來源標記為「網頁」

### 📱 社群媒體爬文
支援自動識別和爬取社群媒體內容：

#### Facebook
- 自動識別 Facebook 貼文連結
- 使用 Apify API 爬取貼文內容、按讚數、留言數、分享數
- AI 生成摘要和分類
- 來源標記為「社群」

#### Instagram
- 自動識別 Instagram 貼文/Reel 連結
- 使用 Apify API 爬取貼文內容、按讚數、留言數
- AI 生成摘要和分類
- 來源標記為「社群」

### 🏷️ 來源分類
所有摘要筆記都會自動標記來源類型：
- **社群** - Facebook、Instagram 等社交媒體
- **網頁** - 一般網站文章
- **文字** - 使用 `/a` 指令的純文字內容

## 環境需求

- Python 3.13+
- uv (套件管理工具)
- LINE Bot 帳號
- OpenAI API Key
- Notion API Key 和資料庫
- Google Drive API 憑證
- Apify API Key

## 安裝步驟

### 1. 複製環境變數範本
```bash
cp .env.example .env
```

### 2. 設定 LINE Bot

到 [LINE Developers Console](https://developers.line.biz/console/) 建立 Messaging API channel：
- 取得 **Channel Access Token**
- 取得 **Channel Secret**
- 填入 `.env` 檔案

### 3. 設定 OpenAI API

到 [OpenAI Platform](https://platform.openai.com/api-keys) 取得 API Key：
- 建立新的 API Key
- 填入 `.env` 的 `OPENAI_API_KEY`

### 4. 設定 Notion

到 [Notion Integrations](https://www.notion.so/my-integrations) 建立 integration：
- 建立新的 integration 並取得 API Key
- 建立三個資料庫（或使用現有的）：
  - **語音筆記資料庫**：需要欄位 `Name`、`Content`、`Created`、`Duration`、`Tags`
  - **摘要筆記資料庫**：需要欄位 `Name`、`Content`、`Summary`、`Category`、`Source`、`Created`
  - **圖片資料庫**：需要欄位 `Name`、`Description`、`Drive_Link`、`Tags`、`Created`
- 將資料庫分享給你的 integration
- 複製每個資料庫的 ID（從 URL 取得）填入 `.env`

**Notion Source 欄位設定：**
在摘要筆記資料庫中新增 `Source` 欄位（Select 類型），並建立以下選項：
- 社群
- 網頁
- 文字

### 5. 設定 Google Drive

1. 到 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案或選擇現有專案
3. 啟用 Google Drive API
4. 建立 OAuth 2.0 憑證
5. 下載憑證檔案並命名為 `credentials.json`
6. 執行授權流程：
   ```bash
   python setup_google_auth.py
   ```
7. （選填）建立 Google Drive 資料夾並取得資料夾 ID 填入 `.env`

### 6. 設定 Apify API

到 [Apify Console](https://console.apify.com/) 取得 API Key：
- 註冊或登入 Apify
- 到 Settings > Integrations 取得 API Token
- 填入 `.env` 的 `APIFY_API_KEY`

### 7. 安裝依賴

```bash
# 使用 uv 安裝
uv sync

# 或使用 pip
pip install -r requirements.txt
```

## 執行方式

### 本地開發

```bash
# 使用 uv
uv run app.py

# 或先啟動虛擬環境
source .venv/bin/activate
python app.py
```

預設服務會在 `http://localhost:5001` 啟動（避免與 macOS AirPlay 的 port 5000 衝突）。

### 設定 Webhook

1. 使用 ngrok 將本機服務暴露到公開網路：
   ```bash
   ngrok http 5001
   ```

2. 複製 ngrok 提供的 HTTPS URL

3. 到 LINE Developers Console 設定 Webhook URL：
   ```
   https://your-ngrok-url.ngrok-free.app/webhook
   ```

4. 點擊 "Verify" 測試連接

5. 啟用 "Use webhook"

## 使用方式

### 語音筆記
直接在 LINE 中傳送語音訊息，Bot 會：
1. 回覆「🎤 收到語音訊息，正在處理中...」
2. 轉換語音為文字
3. 生成標籤
4. 儲存到 Notion
5. 推送結果通知

### 文字摘要
```
/a 這是一段很長的文章內容，需要摘要...
```

Bot 會：
1. 回覆「📝 收到文字內容，正在生成摘要...」
2. 生成摘要和分類
3. 儲存到 Notion（標記來源為「文字」）
4. 推送結果通知

### 圖片分析
直接在 LINE 中傳送圖片，Bot 會：
1. 回覆「🖼️ 收到圖片，正在分析並上傳到 Google Drive...」
2. 使用 AI 分析圖片內容
3. 上傳到 Google Drive
4. 儲存資訊到 Notion
5. 推送 Google Drive 連結

### 網頁摘要
貼上任何網址，例如：
```
https://example.com/article
```

Bot 會：
1. 回覆「🔗 偵測到 URL，正在抓取並生成摘要...」
2. 爬取網頁內容
3. 生成摘要和分類
4. 儲存到 Notion（標記來源為「網頁」）
5. 推送結果通知

### Facebook 貼文摘要
貼上 Facebook 貼文連結，例如：
```
https://www.facebook.com/share/p/xxxxx/
```

Bot 會：
1. 回覆「🔗 偵測到 Facebook 連結，正在抓取並生成摘要...」
2. 使用 Apify 爬取貼文內容
3. 生成摘要和分類
4. 儲存到 Notion（標記來源為「社群」）
5. 推送結果通知

### Instagram 貼文摘要
貼上 Instagram 貼文或 Reel 連結，例如：
```
https://www.instagram.com/p/xxxxx/
https://www.instagram.com/reel/xxxxx/
```

Bot 會：
1. 回覆「🔗 偵測到 Instagram 連結，正在抓取並生成摘要...」
2. 使用 Apify 爬取貼文內容
3. 生成摘要和分類
4. 儲存到 Notion（標記來源為「社群」）
5. 推送結果通知

## 技術架構

- **Flask** - Web 框架
- **LINE Messaging API** - LINE Bot 整合
- **OpenAI API** - 語音轉文字 (Whisper)、圖片分析 (Vision)、文字摘要 (GPT-4)
- **Notion API** - 資料儲存
- **Google Drive API** - 圖片儲存
- **Apify API** - 社群媒體爬蟲
- **BeautifulSoup4** - 網頁爬取

## 專案結構

```
.
├── app.py                 # 主程式
├── google_drive.py        # Google Drive 上傳功能
├── setup_google_auth.py   # Google OAuth 授權設定
├── .env                   # 環境變數（不納入版控）
├── .env.example          # 環境變數範本
├── credentials.json       # Google API 憑證（不納入版控）
├── token.json            # Google OAuth token（不納入版控）
├── pyproject.toml        # 專案依賴設定
└── README.md             # 本文件
```

## 注意事項

- 確保所有 API Key 都已正確設定
- Notion 資料庫欄位名稱必須與程式碼中的名稱完全一致
- 語音檔案和圖片會暫存在記憶體中處理，不會儲存到磁碟
- 建議在生產環境使用 gunicorn 或其他 WSGI 伺服器
- Apify API 有免費額度限制，請注意用量

## 疑難排解

### Port 5000 被佔用
macOS 的 AirPlay Receiver 預設使用 port 5000，請：
- 在 `.env` 設定 `PORT=5001`
- 或關閉 AirPlay Receiver

### Notion API 錯誤
- 確認資料庫已分享給 integration
- 確認欄位名稱和類型正確
- 檢查 Database ID 是否正確

### Google Drive 授權失敗
- 刪除 `token.json` 重新授權
- 確認 `credentials.json` 有效
- 檢查 Google Cloud Console 中 API 是否已啟用

### Apify API 錯誤
- 確認 API Key 有效
- 檢查免費額度是否用盡
- 確認爬取的 URL 格式正確

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！
