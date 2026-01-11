import os
import tempfile
from datetime import datetime
from flask import Flask, request, abort
from dotenv import load_dotenv
from openai import OpenAI
from notion_client import Client
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    AudioMessageContent
)

# 載入 .env 檔案
load_dotenv()

app = Flask(__name__)

# 從環境變數取得設定
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise ValueError('請設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數')

if not OPENAI_API_KEY:
    raise ValueError('請設定 OPENAI_API_KEY 環境變數')

if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError('請設定 NOTION_API_KEY 和 NOTION_DATABASE_ID 環境變數')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion_client = Client(auth=NOTION_API_KEY)


def generate_tags(text):
    """使用 OpenAI 根據筆記內容生成標籤"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是一個筆記分類助手。請根據使用者的筆記內容，生成 1-3 個簡短的中文標籤（例如：工作、學習、生活、想法、待辦等）。只回傳標籤，用逗號分隔，不要有其他說明文字。"
                },
                {
                    "role": "user",
                    "content": f"請為以下筆記生成標籤：\n\n{text}"
                }
            ],
            temperature=0.3,
            max_tokens=50
        )
        tags_text = response.choices[0].message.content.strip()
        # 將逗號分隔的標籤轉換成列表
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        return tags
    except Exception as e:
        app.logger.error(f"生成標籤時發生錯誤: {str(e)}")
        return ["未分類"]


def save_to_notion(content, duration_seconds, tags):
    """將筆記儲存到 Notion database"""
    try:
        # 從內容中擷取前 50 個字元作為標題
        title = content[:50] + "..." if len(content) > 50 else content

        # 建立 Notion page
        notion_client.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                },
                "Content": {
                    "rich_text": [
                        {
                            "text": {
                                "content": content
                            }
                        }
                    ]
                },
                "Created": {
                    "date": {
                        "start": datetime.now().isoformat()
                    }
                },
                "Duration": {
                    "number": duration_seconds
                },
                "Tags": {
                    "multi_select": [{"name": tag} for tag in tags]
                }
            }
        )
        return True
    except Exception as e:
        app.logger.error(f"儲存到 Notion 時發生錯誤: {str(e)}")
        return False


@app.route("/webhook", methods=['POST'])
def webhook():
    """Line Bot 的 webhook endpoint"""
    # 取得 X-Line-Signature header
    signature = request.headers['X-Line-Signature']

    # 取得 request body
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")

    # 驗證 signature 並處理 webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """處理文字訊息，並回傳相同的訊息（Echo Bot）"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 回傳使用者傳來的訊息
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )


@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    """處理語音訊息，轉成文字並儲存到 Notion"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)

        try:
            # 獲取語音長度（毫秒轉秒）
            duration_seconds = event.message.duration / 1000

            # 從 Line 下載語音檔案
            message_content = line_bot_blob_api.get_message_content(event.message.id)

            # 將語音內容寫入臨時檔案
            with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as temp_audio:
                temp_audio.write(message_content)
                temp_audio_path = temp_audio.name

            # 使用 OpenAI Whisper API 轉換語音為文字
            with open(temp_audio_path, 'rb') as audio_file:
                transcription = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="zh"  # 設定為中文，也可以設為 None 讓它自動偵測
                )

            # 刪除臨時檔案
            os.unlink(temp_audio_path)

            # 取得轉錄的文字
            transcribed_text = transcription.text

            # 使用 AI 生成標籤
            tags = generate_tags(transcribed_text)

            # 儲存到 Notion
            saved = save_to_notion(transcribed_text, duration_seconds, tags)

            # 準備回覆訊息
            if saved:
                reply_text = f"✅ 已儲存到 Notion\n\n你說：{transcribed_text}\n\n標籤：{', '.join(tags)}"
            else:
                reply_text = f"⚠️ 儲存到 Notion 時發生錯誤\n\n你說：{transcribed_text}"

            # 回傳結果
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

        except Exception as e:
            app.logger.error(f"處理語音訊息時發生錯誤: {str(e)}")
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="抱歉，處理語音訊息時發生錯誤。")]
                )
            )


@app.route("/", methods=['GET'])
def health_check():
    """健康檢查 endpoint"""
    return 'Line Bot is running!', 200


if __name__ == "__main__":
    # 在本地開發時使用
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
