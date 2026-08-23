from flask import Flask, request
import os
import requests

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")

@app.route("/")
def home():
    return "Yubisaki no Meikyu API is alive!"

@app.route("/callback", methods=["POST"])
def callback():
    data = request.get_json()

    print("LINEからWebhookを受信しました！")
    print(data)

    for event in data.get("events", []):
        if event.get("type") == "message":
            reply_token = event.get("replyToken")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
            }

            body = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": "受信しました！"
                    }
                ]
            }

            response = requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                json=body
            )

            print("LINEへの返信結果:", response.status_code)
            print(response.text)

    return "OK", 200
