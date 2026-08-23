from flask import Flask, request
import os
import requests

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")


# ユーザーごとの現在地
user_states = {}


# テスト用の部屋構造
rooms = {
    "あ": {
        "上": None,
        "右": "か",
        "下": None,
        "左": None
    },
    "か": {
        "上": None,
        "右": "な",
        "下": None,
        "左": "あ"
    },
    "な": {
        "上": None,
        "右": None,
        "下": None,
        "左": "か"
    }
}


# フリック入力の仮ルール
flick_directions = {
    "き": "上",
    "こ": "右",
    "く": "下",
    "け": "左"
}


@app.route("/")
def home():
    return "Yubisaki no Meikyu API is alive!"


@app.route("/callback", methods=["POST"])
def callback():
    data = request.get_json()

    print("LINEからWebhookを受信しました！")
    print(data)

    for event in data.get("events", []):

        if event.get("type") != "message":
            continue

        message = event.get("message", {})

        if message.get("type") != "text":
            continue

        text = message.get("text")
        user_id = event.get("source", {}).get("userId")
        reply_token = event.get("replyToken")

        # 初めてのユーザーは「あ」からスタート
        if user_id not in user_states:
            user_states[user_id] = "あ"

        current_room = user_states[user_id]

        # 入力された文字がフリック入力として定義されているか確認
        if text in flick_directions:

            direction = flick_directions[text]

            next_room = rooms[current_room].get(direction)

            if next_room is not None:

                # 移動成功
                user_states[user_id] = next_room

                reply_text = (
                    f"{current_room}の部屋から"
                    f"{next_room}の部屋へ移動しました！\n"
                    f"現在地：{next_room}"
                )

            else:

                # その方向に扉がない
                reply_text = (
                    f"その方向には扉がありません。\n"
                    f"現在地：{current_room}"
                )

        else:

            reply_text = (
                f"現在地：{current_room}\n"
                f"「{text}」は移動入力ではありません。"
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
        }

        body = {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": reply_text
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
