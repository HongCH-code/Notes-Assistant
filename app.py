import os
import tempfile
from flask import Flask, request, abort
from dotenv import load_dotenv
from openai import OpenAI
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

# 從環境變數取得 Line Bot 的設定
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise ValueError('請設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數')

if not OPENAI_API_KEY:
    raise ValueError('請設定 OPENAI_API_KEY 環境變數')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
openai_client = OpenAI(api_key=OPENAI_API_KEY)


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
    """處理語音訊息，將語音轉成文字後回傳"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)

        try:
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

            # 回傳轉錄的文字
            transcribed_text = transcription.text
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"你說：{transcribed_text}")]
                )
            )

        except Exception as e:
            app.logger.error(f"語音轉文字錯誤: {str(e)}")
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="抱歉，語音轉文字時發生錯誤。")]
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
