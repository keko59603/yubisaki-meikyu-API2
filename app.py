from flask import Flask, request
import os
import requests
import psycopg2

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")


# ==========================================
# 部屋の構造
# ==========================================

rooms = {
    "あ": {
        "上": None,
        "右": "か",
        "下": "た",
        "左": None
    },

    "か": {
        "上": None,
        "右": "さ",
        "下": "な",
        "左": "あ"
    },

    "さ": {
        "上": None,
        "右": "DELETE",
        "下": "は",
        "左": "か"
    },

    "た": {
        "上": "あ",
        "右": "な",
        "下": "ま",
        "左": None
    },

    "な": {
        "上": "か",
        "右": "は",
        "下": "や",
        "左": "た"
    },

    "は": {
        "上": "さ",
        "右": None,
        "下": "ら",
        "左": "な"
    },

    "ま": {
        "上": "た",
        "右": "や",
        "下": None,
        "左": None
    },

    "や": {
        "上": "な",
        "右": None,
        "下": "わ",
        "左": None
    },

    "ら": {
        "上": "は",
        "右": None,
        "下": None,
        "左": "や"
    },

    "わ": {
        "上": "や",
        "右": None,
        "下": None,
        "左": None
    }
}


# ==========================================
# フリック入力
# ==========================================

flick_directions = {
    "き": "左",
    "く": "上",
    "け": "右",
    "こ": "下"
}


# ==========================================
# データベース接続
# ==========================================

def get_connection():
    return psycopg2.connect(DATABASE_URL)


# ==========================================
# データベース初期化
# ==========================================

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

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS n_unlocked
        BOOLEAN NOT NULL DEFAULT FALSE
    """)

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS delete_unlocked
        BOOLEAN NOT NULL DEFAULT FALSE
    """)

    connection.commit()

    cursor.close()
    connection.close()


# ==========================================
# ユーザー状態取得
# ==========================================

def get_user_state(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            current_room,
            history,
            n_unlocked,
            delete_unlocked
        FROM players
        WHERE user_id = %s
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    if result is None:

        current_room = "か"
        history = ""
        n_unlocked = False
        delete_unlocked = False

        cursor.execute(
            """
            INSERT INTO players
            (
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked
            )
        )

        connection.commit()

    else:

        current_room = result[0]
        history = result[1]
        n_unlocked = result[2]
        delete_unlocked = result[3]

    cursor.close()
    connection.close()

    return (
        current_room,
        history,
        n_unlocked,
        delete_unlocked
    )


# ==========================================
# ユーザー状態保存
# ==========================================

def update_user_state(
    user_id,
    current_room,
    history,
    n_unlocked,
    delete_unlocked
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE players
        SET
            current_room = %s,
            history = %s,
            n_unlocked = %s,
            delete_unlocked = %s
        WHERE user_id = %s
        """,
        (
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            user_id
        )
    )

    connection.commit()

    cursor.close()
    connection.close()


# ==========================================
# ホーム
# ==========================================

@app.route("/")
def home():

    return "Yubisaki no Meikyu API is alive!"


# ==========================================
# LINE Webhook
# ==========================================

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

        user_id = event.get(
            "source",
            {}
        ).get("userId")

        reply_token = event.get(
            "replyToken"
        )

        (
            current_room,
            history,
            n_unlocked,
            delete_unlocked
        ) = get_user_state(user_id)


        # ==================================
        # 移動入力
        # ==================================

        if text in flick_directions:

            direction = flick_directions[text]

            next_room = rooms[current_room].get(
                direction
            )


            # ==================================
            # 扉がない
            # ==================================

            if next_room is None:

                reply_text = (
                    "その方向には進めません。\n"
                    f"現在地：{current_room}"
                )


            # ==================================
            # 削除ボタン
            # ==================================

            elif next_room == "DELETE":

                if not delete_unlocked:

                    reply_text = (
                        "その扉はまだ開いていません。\n"
                        f"現在地：{current_room}"
                    )

                else:

                    current_room = "か"
                    history = ""

                    update_user_state(
                        user_id,
                        current_room,
                        history,
                        n_unlocked,
                        delete_unlocked
                    )

                    reply_text = (
                        "入力をリセットしました。\n"
                        "現在地：か"
                    )


            # ==================================
            # 「な」への扉
            # ==================================

            elif next_room == "な":

                if not n_unlocked:

                    reply_text = (
                        "その扉はまだロックされています。\n"
                        f"現在地：{current_room}"
                    )

                else:

                    current_room = next_room

                    if history:
                        history += "," + text
                    else:
                        history = text

                    update_user_state(
                        user_id,
                        current_room,
                        history,
                        n_unlocked,
                        delete_unlocked
                    )

                    reply_text = (
                        f"{current_room}の部屋へ移動しました！\n"
                        f"現在地：{current_room}"
                    )


            # ==================================
            # 通常移動
            # ==================================

            else:

                current_room = next_room

                if history:
                    history += "," + text
                else:
                    history = text


                # ==================================
                # わの部屋に到達
                # ==================================

                if current_room == "わ":

                    n_unlocked = True
                    delete_unlocked = True

                    reply_text = (
                        "わの部屋へ移動しました！\n"
                        "新たな扉のロックが解除されたようです。\n"
                        f"現在地：{current_room}"
                    )

                else:

                    reply_text = (
                        f"{current_room}の部屋へ移動しました！\n"
                        f"現在地：{current_room}"
                    )


                update_user_state(
                    user_id,
                    current_room,
                    history,
                    n_unlocked,
                    delete_unlocked
                )


        # ==================================
        # 移動入力ではない
        # ==================================

        else:

            reply_text = (
                f"現在地：{current_room}\n"
                f"「{text}」は移動入力ではありません。"
            )


        # ==================================
        # LINEへ返信
        # ==================================

        headers = {
            "Content-Type": "application/json",
            "Authorization": (
                f"Bearer {CHANNEL_ACCESS_TOKEN}"
            )
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

        print(
            "LINEへの返信結果:",
            response.status_code
        )

        print(response.text)


    return "OK", 200


# ==========================================
# 起動時にDBを準備
# ==========================================

initialize_database()
