from flask import Flask, request
import os
import requests
import psycopg2

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")


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


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id TEXT PRIMARY KEY,
            current_room TEXT NOT NULL,
            history TEXT NOT NULL
        )
    """)

    connection.commit()
    cursor.close()
    connection.close()


def get_user_state(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT current_room, history
        FROM players
        WHERE user_id = %s
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    if result is None:
        current_room = "あ"
        history = ""

        cursor.execute(
            """
            INSERT INTO players (user_id, current_room, history)
            VALUES (%s, %s, %s)
            """,
            (user_id, current_room, history)
        )

        connection.commit()

    else:
        current_room = result[0]
        history = result[1]

    cursor.close()
    connection.close()

    return current_room, history


def update_user_state(user_id, current_room, history):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE players
        SET current_room = %s,
            history = %s
        WHERE user_id = %s
        """,
        (current_room, history, user_id)
    )

    connection.commit()
    cursor.close()
    connection.close()


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

        current_room, history = get_user_state(user_id)

        if text in flick_directions:

            direction = flick_directions[text]
            next_room = rooms[current_room].get(direction)

            if next_room is not None:

                current_room = next_room

                if history:
                    history += "," + text
                else:
                    history = text

                update_user_state(
                    user_id,
                    current_room,
                    history
                )

                history_display = " → ".join(history.split(","))

                reply_text = (
                    f"{current_room}の部屋へ移動しました！\n"
                    f"現在地：{current_room}\n"
                    f"履歴：{history_display}"
                )

            else:

                history_display = (
                    " → ".join(history.split(","))
                    if history
                    else "なし"
                )

                reply_text = (
                    f"その方向には扉がありません。\n"
                    f"現在地：{current_room}\n"
                    f"履歴：{history_display}"
                )

        else:

            history_display = (
                " → ".join(history.split(","))
                if history
                else "なし"
            )

            reply_text = (
                f"現在地：{current_room}\n"
                f"「{text}」は移動入力ではありません。\n"
                f"履歴：{history_display}"
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


# アプリ起動時にDBを準備
initialize_database()
