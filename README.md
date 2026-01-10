# Line Echo Bot

這是一個簡單的 Line Echo Bot，會將使用者傳送的訊息原封不動地回傳。

## 環境需求

- Python 3.13+
- uv (套件管理工具)

## 安裝步驟

1. 複製 `.env.example` 為 `.env` 並填入你的 Line Bot 憑證：
   ```bash
   cp .env.example .env
   ```

2. 到 [Line Developers Console](https://developers.line.biz/console/) 建立 Messaging API channel，並取得：
   - Channel Access Token
   - Channel Secret

3. 將憑證填入 `.env` 檔案

## 執行方式

使用 uv 執行：
```bash
uv run app.py
```

或者先啟動虛擬環境：
```bash
source .venv/bin/activate
python app.py
```

服務會在 `http://localhost:5000` 啟動。

## 設定 Webhook

1. 使用 ngrok 或其他工具將本機服務暴露到公開網路：
   ```bash
   ngrok http 5000
   ```

2. 在 Line Developers Console 設定 Webhook URL：
   ```
   https://your-ngrok-url.ngrok.io/callback
   ```

3. 啟用 Webhook

## 功能

- Echo Bot：將使用者傳送的文字訊息原封不動地回傳
