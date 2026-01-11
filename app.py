import os
import tempfile
import threading
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
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    AudioMessageContent,
    ImageMessageContent
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
NOTION_SUMMARY_DATABASE_ID = os.getenv('NOTION_SUMMARY_DATABASE_ID')
NOTION_IMAGE_DATABASE_ID = os.getenv('NOTION_IMAGE_DATABASE_ID')
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
GOOGLE_TOKEN_PATH = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise ValueError('請設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數')

if not OPENAI_API_KEY:
    raise ValueError('請設定 OPENAI_API_KEY 環境變數')

if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError('請設定 NOTION_API_KEY 和 NOTION_DATABASE_ID 環境變數')

if not NOTION_SUMMARY_DATABASE_ID:
    raise ValueError('請設定 NOTION_SUMMARY_DATABASE_ID 環境變數')

if not NOTION_IMAGE_DATABASE_ID:
    raise ValueError('請設定 NOTION_IMAGE_DATABASE_ID 環境變數')

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
    """將語音筆記儲存到 Notion database"""
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


def generate_summary_and_category(text):
    """使用 OpenAI 生成文字摘要和內容分類"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """你是一個文字摘要助手。請分析使用者提供的文字，並回傳 JSON 格式的結果，包含：
1. category: 內容類別（單一類別，例如：工作、學習、新聞、生活、想法、技術、商業等）
2. summary: 重點摘要（濃縮成 2-3 句話，保留關鍵資訊）

請只回傳 JSON，不要有其他文字。"""
                },
                {
                    "role": "user",
                    "content": f"請分析以下文字：\n\n{text}"
                }
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        import json
        result = json.loads(response.choices[0].message.content)
        return result.get('summary', ''), result.get('category', '未分類')
    except Exception as e:
        app.logger.error(f"生成摘要時發生錯誤: {str(e)}")
        # 如果失敗，返回簡單的摘要
        simple_summary = text[:200] + "..." if len(text) > 200 else text
        return simple_summary, "未分類"


def analyze_image_with_vision(image_bytes):
    """使用 OpenAI Vision API 分析圖片內容"""
    try:
        import base64
        import json

        # 將圖片編碼為 base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """你是一個圖片分析助手。請分析圖片並回傳 JSON 格式：
1. description: 圖片的詳細描述（2-3 句話，描述主要內容、場景、物體等）
2. tags: 內容標籤（3-5 個中文標籤，例如：風景、食物、人物、工作、生活等）

請只回傳 JSON，不要有其他文字。"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "請分析這張圖片"
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        description = result.get('description', '圖片內容')
        tags = result.get('tags', ['未分類'])

        # 確保 tags 是列表
        if isinstance(tags, str):
            tags = [tags]

        return description, tags
    except Exception as e:
        app.logger.error(f"分析圖片時發生錯誤: {str(e)}")
        return "圖片內容", ["未分類"]


def save_summary_to_notion(content, summary, category):
    """將文字摘要儲存到 Notion summary database"""
    try:
        # 從摘要中擷取前 50 個字元作為標題
        title = summary[:50] + "..." if len(summary) > 50 else summary

        # 建立 Notion page
        notion_client.pages.create(
            parent={"database_id": NOTION_SUMMARY_DATABASE_ID},
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
                "Category": {
                    "multi_select": [
                        {
                            "name": category
                        }
                    ]
                },
                "Summary": {
                    "rich_text": [
                        {
                            "text": {
                                "content": summary
                            }
                        }
                    ]
                },
                "Created": {
                    "date": {
                        "start": datetime.now().isoformat()
                    }
                }
            }
        )
        return True
    except Exception as e:
        app.logger.error(f"儲存摘要到 Notion 時發生錯誤: {str(e)}")
        return False


def save_image_to_notion(title, description, tags, drive_link):
    """將圖片資訊儲存到 Notion image database"""
    try:
        notion_client.pages.create(
            parent={"database_id": NOTION_IMAGE_DATABASE_ID},
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
                "Description": {
                    "rich_text": [
                        {
                            "text": {
                                "content": description
                            }
                        }
                    ]
                },
                "Drive_Link": {
                    "url": drive_link
                },
                "Tags": {
                    "multi_select": [{"name": tag} for tag in tags]
                },
                "Created": {
                    "date": {
                        "start": datetime.now().isoformat()
                    }
                }
            }
        )
        return True
    except Exception as e:
        app.logger.error(f"儲存圖片到 Notion 時發生錯誤: {str(e)}")
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


def process_summary_background(text, user_id):
    """背景處理文字摘要的函數"""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # 使用 AI 生成摘要和分類
            summary, category = generate_summary_and_category(text)

            # 儲存到 Notion
            saved = save_summary_to_notion(text, summary, category)

            # 準備推送訊息
            if saved:
                push_text = f"✅ 已儲存到 Notion\n\n📝 摘要：{summary}\n\n📁 類別：{category}"
            else:
                push_text = f"⚠️ 儲存到 Notion 時發生錯誤\n\n📝 摘要：{summary}\n\n📁 類別：{category}"

            # 使用 push message 發送結果
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=push_text)]
                )
            )

    except Exception as e:
        app.logger.error(f"背景處理文字摘要時發生錯誤: {str(e)}")
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text="抱歉，處理文字摘要時發生錯誤。")]
                    )
                )
        except:
            pass


def process_image_background(message_id, user_id):
    """背景處理圖片訊息的函數"""
    try:
        # 導入 Google Drive 模組
        from google_drive import upload_image_to_drive

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_blob_api = MessagingApiBlob(api_client)

            # 1. 下載圖片
            image_content = line_bot_blob_api.get_message_content(message_id)
            image_bytes = image_content

            # 2. 使用 Vision API 分析圖片
            description, tags = analyze_image_with_vision(image_bytes)

            # 3. 生成標題（使用描述的前 50 個字）
            title = description[:50] + "..." if len(description) > 50 else description

            # 4. 上傳到 Google Drive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linebot_image_{timestamp}.jpg"

            drive_result = upload_image_to_drive(
                image_bytes,
                filename,
                folder_id=GOOGLE_DRIVE_FOLDER_ID
            )

            if not drive_result:
                raise Exception("上傳到 Google Drive 失敗")

            drive_link = drive_result['web_view_link']

            # 5. 儲存到 Notion
            saved = save_image_to_notion(title, description, tags, drive_link)

            # 6. 發送結果通知
            if saved:
                tags_str = ', '.join(tags)
                push_text = f"""✅ 圖片已儲存

📝 描述：{description}

🏷️ 標籤：{tags_str}

🔗 Google Drive: {drive_link}"""
            else:
                push_text = f"⚠️ 儲存到 Notion 時發生錯誤\n\n圖片已上傳到 Drive: {drive_link}"

            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=push_text)]
                )
            )

    except Exception as e:
        app.logger.error(f"背景處理圖片訊息時發生錯誤: {str(e)}")
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=f"抱歉，處理圖片時發生錯誤：{str(e)}")]
                    )
                )
        except:
            pass


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """處理文字訊息，支援 /a 指令進行文字摘要"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        try:
            text = event.message.text.strip()

            # 檢查是否為 /a 指令（文字摘要功能）
            if text.startswith('/a'):
                # 提取實際內容（去掉 /a 指令）
                content = text[2:].strip()

                if not content:
                    # 如果沒有內容，提示用戶
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請在 /a 後面加上要摘要的文字內容\n\n範例：\n/a 這是一段很長的文章內容...")]
                        )
                    )
                    return

                # 立即回覆「處理中」
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="📝 收到文字內容，正在生成摘要...")]
                    )
                )

                # 啟動背景線程處理摘要
                user_id = event.source.user_id
                thread = threading.Thread(
                    target=process_summary_background,
                    args=(content, user_id)
                )
                thread.daemon = True
                thread.start()

            else:
                # 一般文字訊息，Echo Bot 行為
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=text)]
                    )
                )

        except Exception as e:
            app.logger.error(f"處理文字訊息時發生錯誤: {str(e)}")
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="抱歉，處理訊息時發生錯誤。")]
                )
            )


def process_audio_background(message_id, user_id, duration_seconds):
    """背景處理語音訊息的函數"""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_blob_api = MessagingApiBlob(api_client)

            # 從 Line 下載語音檔案
            message_content = line_bot_blob_api.get_message_content(message_id)

            # 將語音內容寫入臨時檔案
            with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as temp_audio:
                temp_audio.write(message_content)
                temp_audio_path = temp_audio.name

            # 使用 OpenAI Whisper API 轉換語音為文字
            with open(temp_audio_path, 'rb') as audio_file:
                transcription = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="zh"
                )

            # 刪除臨時檔案
            os.unlink(temp_audio_path)

            # 取得轉錄的文字
            transcribed_text = transcription.text

            # 使用 AI 生成標籤
            tags = generate_tags(transcribed_text)

            # 儲存到 Notion
            saved = save_to_notion(transcribed_text, duration_seconds, tags)

            # 準備推送訊息
            if saved:
                push_text = f"✅ 已儲存到 Notion\n\n你說：{transcribed_text}\n\n標籤：{', '.join(tags)}"
            else:
                push_text = f"⚠️ 儲存到 Notion 時發生錯誤\n\n你說：{transcribed_text}"

            # 使用 push message 發送結果
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=push_text)]
                )
            )

    except Exception as e:
        app.logger.error(f"背景處理語音訊息時發生錯誤: {str(e)}")
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text="抱歉，處理語音訊息時發生錯誤。")]
                    )
                )
        except:
            pass


@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    """處理語音訊息，立即回應並在背景處理"""
    # 立即回應 Line，避免 timeout
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        try:
            # 獲取必要資訊
            message_id = event.message.id
            user_id = event.source.user_id
            duration_seconds = event.message.duration / 1000

            # 立即回覆「處理中」
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="🎤 收到語音訊息，正在處理中...")]
                )
            )

            # 啟動背景線程處理
            thread = threading.Thread(
                target=process_audio_background,
                args=(message_id, user_id, duration_seconds)
            )
            thread.daemon = True
            thread.start()

        except Exception as e:
            app.logger.error(f"處理語音訊息時發生錯誤: {str(e)}")
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="抱歉，處理語音訊息時發生錯誤。")]
                )
            )


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    """處理圖片訊息，立即回應並在背景處理"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        try:
            message_id = event.message.id
            user_id = event.source.user_id

            # 立即回覆
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="🖼️ 收到圖片，正在分析並上傳到 Google Drive...")]
                )
            )

            # 背景處理
            thread = threading.Thread(
                target=process_image_background,
                args=(message_id, user_id)
            )
            thread.daemon = True
            thread.start()

        except Exception as e:
            app.logger.error(f"處理圖片訊息時發生錯誤: {str(e)}")
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="抱歉，處理圖片訊息時發生錯誤。")]
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
