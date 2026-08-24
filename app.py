from flask import Flask, request, send_from_directory
import os
import requests
import psycopg2

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")


rooms = {
    "あ": {"上": None, "右": "か", "下": "た", "左": None},
    "か": {"上": None, "右": "さ", "下": "な", "左": "あ"},
    "さ": {"上": None, "右": "DELETE", "下": "は", "左": "か"},
    "た": {"上": "あ", "右": "な", "下": "ま", "左": None},
    "な": {"上": "か", "右": "は", "下": "や", "左": "た"},
    "は": {"上": "さ", "右": None, "下": "ら", "左": "な"},
    "ま": {"上": "た", "右": "や", "下": None, "左": None},
    "や": {"上": "な", "右": None, "下": "わ", "左": None},
    "ら": {"上": "は", "右": None, "下": None, "左": "や"},
    "わ": {"上": "や", "右": None, "下": None, "左": None}
}


room_inputs = {
    "あ": {"い": "左", "う": "上", "え": "右", "お": "下"},
    "か": {"き": "左", "く": "上", "け": "右", "こ": "下"},
    "さ": {"し": "左", "す": "上", "せ": "右", "そ": "下"},
    "た": {"ち": "左", "つ": "上", "て": "右", "と": "下"},
    "な": {"に": "左", "ぬ": "上", "ね": "右", "の": "下"},
    "は": {"ひ": "左", "ふ": "上", "へ": "右", "ほ": "下"},
    "ま": {"み": "左", "む": "上", "め": "右", "も": "下"},
    "や": {"い": "左", "ゆ": "上", "え": "右", "よ": "下"},
    "ら": {"り": "左", "る": "上", "れ": "右", "ろ": "下"},
    "わ": {"ゐ": "左", "う": "上", "ゑ": "右", "を": "下", "ん": "上"}
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

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS n_unlocked BOOLEAN NOT NULL DEFAULT FALSE
    """)

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS delete_unlocked BOOLEAN NOT NULL DEFAULT FALSE
    """)

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS wa_reached BOOLEAN NOT NULL DEFAULT FALSE
    """)

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS game_clear BOOLEAN NOT NULL DEFAULT FALSE
    """)

    connection.commit()
    cursor.close()
    connection.close()


def get_user_state(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear
        FROM players
        WHERE user_id = %s
    """, (user_id,))

    result = cursor.fetchone()

    if result is None:
        current_room = "か"
        history = ""
        n_unlocked = False
        delete_unlocked = False
        wa_reached = False
        game_clear = False

        cursor.execute("""
            INSERT INTO players (
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear
        ))

        connection.commit()

    else:
        current_room = result[0]
        history = result[1]
        n_unlocked = result[2]
        delete_unlocked = result[3]
        wa_reached = result[4]
        game_clear = result[5]

    cursor.close()
    connection.close()

    return (
        current_room,
        history,
        n_unlocked,
        delete_unlocked,
        wa_reached,
        game_clear
    )


def update_user_state(
    user_id,
    current_room,
    history,
    n_unlocked,
    delete_unlocked,
    wa_reached,
    game_clear
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE players
        SET
            current_room = %s,
            history = %s,
            n_unlocked = %s,
            delete_unlocked = %s,
            wa_reached = %s,
            game_clear = %s
        WHERE user_id = %s
    """, (
        current_room,
        history,
        n_unlocked,
        delete_unlocked,
        wa_reached,
        game_clear,
        user_id
    ))

    connection.commit()
    cursor.close()
    connection.close()


@app.route("/")
def home():
    return "Yubisaki no Meikyu API is alive!"


@app.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory("images", filename)


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


        # ==============================
        # 画像テスト
        # ==============================

        if text == "画像テスト":

            image_url = request.host_url.rstrip("/") + "/images/test.png"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
            }

            body = {
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "image",
                        "originalContentUrl": image_url,
                        "previewImageUrl": image_url
                    }
                ]
            }

            response = requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=headers,
                json=body
            )

            print("LINEへの画像返信結果:", response.status_code)
            print(response.text)

            continue


        # ==============================
        # 現在の状態を取得
        # ==============================

        (
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear
        ) = get_user_state(user_id)


        # ==============================
        # オールリセット
        # ==============================

        if text == "オールリセット":

            current_room = "か"
            history = ""
            n_unlocked = False
            delete_unlocked = False
            wa_reached = False
            game_clear = False

            update_user_state(
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear
            )

            reply_text = "すべての記録をリセットしました。\n現在地：か"


        # ==============================
        # 履歴リセット
        # ==============================

        elif text == "履歴リセット":

            current_room = "か"
            history = ""

            update_user_state(
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear
            )

            reply_text = "履歴をリセットしました。\n現在地：か"


        # ==============================
        # 状態確認
        # ==============================

        elif text == "状態確認":

            if user_id != ADMIN_USER_ID:
                reply_text = "このコマンドは使用できません。"

            else:

                history_display = (
                    " → ".join(history.split(","))
                    if history
                    else "なし"
                )

                reply_text = (
                    "【現在の状態】\n"
                    f"現在地：{current_room}\n"
                    f"入力履歴：{history_display}\n"
                    f"な解放：{'ON' if n_unlocked else 'OFF'}\n"
                    f"削除部屋：{'ON' if delete_unlocked else 'OFF'}\n"
                    f"わ到達：{'ON' if wa_reached else 'OFF'}\n"
                    f"ゲームクリア：{'ON' if game_clear else 'OFF'}"
                )


        # ==============================
        # ゲームクリア済み
        # ==============================

        elif game_clear:

            reply_text = (
                "このゲームはすでにクリアしています！\n"
                "もう一度遊ぶ場合は「オールリセット」と入力してください。"
            )


        # ==============================
        # 移動処理
        # ==============================

        else:

            direction = room_inputs.get(
                current_room,
                {}
            ).get(text)


            # ==========================
            # 移動入力ではない
            # ==========================

            if direction is None:

                reply_text = (
                    f"現在地：{current_room}\n"
                    f"「{text}」はこの部屋の移動入力ではありません。"
                )


            else:

                next_room = rooms[current_room].get(direction)


                # ======================
                # 扉がない
                # ======================

                if next_room is None:

                    reply_text = (
                        "その方向には進めません。\n"
                        f"現在地：{current_room}"
                    )


                # ======================
                # 削除部屋
                # ======================

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
                            delete_unlocked,
                            wa_reached,
                            game_clear
                        )

                        reply_text = (
                            "履歴をリセットしました。\n"
                            "現在地：か"
                        )


                # ======================
                # なへの扉
                # ======================

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
                            delete_unlocked,
                            wa_reached,
                            game_clear
                        )

                        reply_text = (
                            f"{current_room}の部屋に移動しました！\n"
                            f"現在地：{current_room}"
                        )


                # ======================
                # 通常移動
                # ======================

                else:

                    current_room = next_room

                    if history:
                        history += "," + text
                    else:
                        history = text


                    # ==================
                    # わの部屋
                    # ==================

                    if current_room == "わ":

                        # ------------------
                        # ゲームクリア
                        # ------------------

                        if history == "こ,の,よ":

                            game_clear = True

                            update_user_state(
                                user_id,
                                current_room,
                                history,
                                n_unlocked,
                                delete_unlocked,
                                wa_reached,
                                game_clear
                            )

                            reply_text = (
                                "🎉 ゲームクリア！ 🎉\n\n"
                                "こ → の → よ\n"
                                "おめでとうございます！"
                            )


                        # ------------------
                        # 初めてわに到達
                        # ------------------

                        elif not wa_reached:

                            wa_reached = True
                            n_unlocked = True
                            delete_unlocked = True

                            update_user_state(
                                user_id,
                                current_room,
                                history,
                                n_unlocked,
                                delete_unlocked,
                                wa_reached,
                                game_clear
                            )

                            answer_text = "".join(
                                history.split(",")
                            )

                            base_url = request.host_url.rstrip("/")

                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
                            }

                            body = {
                                "replyToken": reply_token,
                                "messages": [
                                    {
                                        "type": "text",
                                        "text": "どこかの扉のロックが解除された。"
                                    },
                                    {
                                        "type": "image",
                                        "originalContentUrl": base_url + "/images/wa.png",
                                        "previewImageUrl": base_url + "/images/wa.png"
                                    },
                                    {
                                        "type": "image",
                                        "originalContentUrl": base_url + "/images/final.png",
                                        "previewImageUrl": base_url + "/images/final.png"
                                    },
                                    {
                                        "type": "text",
                                        "text": "解答欄：" + answer_text
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

                            continue


                        # ------------------
                        # 2回目以降のわ
                        # ------------------

                        else:

                            update_user_state(
                                user_id,
                                current_room,
                                history,
                                n_unlocked,
                                delete_unlocked,
                                wa_reached,
                                game_clear
                            )

                            answer_text = "".join(
                                history.split(",")
                            )

                            base_url = request.host_url.rstrip("/")

                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
                            }

                            body = {
                                "replyToken": reply_token,
                                "messages": [
                                    {
                                        "type": "image",
                                        "originalContentUrl": base_url + "/images/wa.png",
                                        "previewImageUrl": base_url + "/images/wa.png"
                                    },
                                    {
                                        "type": "image",
                                        "originalContentUrl": base_url + "/images/final.png",
                                        "previewImageUrl": base_url + "/images/final.png"
                                    },
                                    {
                                        "type": "text",
                                        "text": "解答欄：" + answer_text
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

                            continue


                    # ==================
                    # その他の部屋
                    # ==================

                    else:

                        update_user_state(
                            user_id,
                            current_room,
                            history,
                            n_unlocked,
                            delete_unlocked,
                            wa_reached,
                            game_clear
                        )

                        reply_text = (
                            f"{current_room}の部屋に移動しました！\n"
                            f"現在地：{current_room}"
                        )


        # ==============================
        # LINEへ通常返信
        # ==============================

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


initialize_database()
