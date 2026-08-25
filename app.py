from flask import Flask, request, send_from_directory
import os
import requests
import psycopg2

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")


# ==========================================
# 部屋の構造
# ==========================================

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


# ==========================================
# 各部屋で入力できる文字
# ==========================================

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


# ==========================================
# 方向の反転
# ==========================================

opposite_direction = {
    "上": "下",
    "下": "上",
    "左": "右",
    "右": "左"
}


# ==========================================
# プレイヤー視点から見た移動方向
# ==========================================

def get_relative_direction(view_direction, move_direction):

    relative_directions = {
        "上": {
            "上": "前",
            "右": "右",
            "下": "後ろ",
            "左": "左"
        },
        "右": {
            "上": "左",
            "右": "前",
            "下": "右",
            "左": "後ろ"
        },
        "下": {
            "上": "後ろ",
            "右": "左",
            "下": "前",
            "左": "右"
        },
        "左": {
            "上": "右",
            "右": "後ろ",
            "下": "左",
            "左": "前"
        }
    }

    return relative_directions[view_direction][move_direction]


# ==========================================
# 部屋名 → 画像用ファイル名
# ==========================================

room_image_names = {
    "あ": "a",
    "か": "ka",
    "さ": "sa",
    "た": "ta",
    "な": "na",
    "は": "ha",
    "ま": "ma",
    "や": "ya",
    "ら": "ra",
    "わ": "wa"
}


# ==========================================
# DB接続
# ==========================================

def get_connection():
    return psycopg2.connect(DATABASE_URL)


# ==========================================
# DB初期化
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

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS entry_direction TEXT
    """)

    cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS view_direction TEXT
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

    cursor.execute("""
        SELECT
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear,
            entry_direction,
            view_direction
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

        # 最初の部屋はどこからも入っていない
        entry_direction = None

        # 最初の向き
        view_direction = "下"

        cursor.execute("""
            INSERT INTO players (
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear,
                entry_direction,
                view_direction
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear,
            entry_direction,
            view_direction
        ))

        connection.commit()

    else:

        current_room = result[0]
        history = result[1]
        n_unlocked = result[2]
        delete_unlocked = result[3]
        wa_reached = result[4]
        game_clear = result[5]
        entry_direction = result[6]
        view_direction = result[7]

    cursor.close()
    connection.close()

    return (
        current_room,
        history,
        n_unlocked,
        delete_unlocked,
        wa_reached,
        game_clear,
        entry_direction,
        view_direction
    )


# ==========================================
# ユーザー状態更新
# ==========================================

def update_user_state(
    user_id,
    current_room,
    history,
    n_unlocked,
    delete_unlocked,
    wa_reached,
    game_clear,
    entry_direction,
    view_direction
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
            game_clear = %s,
            entry_direction = %s,
            view_direction = %s
        WHERE user_id = %s
    """, (
        current_room,
        history,
        n_unlocked,
        delete_unlocked,
        wa_reached,
        game_clear,
        entry_direction,
        view_direction,
        user_id
    ))

    connection.commit()

    cursor.close()
    connection.close()


# ==========================================
# 画像URLを作る
# ==========================================

def get_room_image_url(room, direction):

    if direction not in ["上", "下", "左", "右"]:
        return None

    room_name = room_image_names.get(room)

    if room_name is None:
        return None

    direction_names = {
        "上": "up",
        "下": "down",
        "左": "left",
        "右": "right"
    }

    filename = (
        f"{room_name}_{direction_names[direction]}.png"
    )

    base_url = request.host_url.rstrip("/")

    return f"{base_url}/images/{filename}"


# ==========================================
# LINEへ画像を返信する
# ==========================================

def reply_image(reply_token, image_url, reply_text=None):

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    messages = []

    if reply_text:
        messages.append({
            "type": "text",
            "text": reply_text
        })

    messages.append({
        "type": "image",
        "originalContentUrl": image_url,
        "previewImageUrl": image_url
    })

    body = {
        "replyToken": reply_token,
        "messages": messages
    }

    response = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        json=body
    )

    print(
        "LINEへの画像＋テキスト返信結果:",
        response.status_code
    )

    print(response.text)

    return response


# ==========================================
# トップページ
# ==========================================

@app.route("/")
def home():

    return "Yubisaki no Meikyu API is alive!"


# ==========================================
# 画像配信
# ==========================================

@app.route("/images/<filename>")
def serve_image(filename):

    return send_from_directory("images", filename)


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
        user_id = event.get("source", {}).get("userId")
        reply_token = event.get("replyToken")


        # ======================================
        # 状態取得
        # ======================================

        (
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear,
            entry_direction,
            view_direction
        ) = get_user_state(user_id)


        # ======================================
        # 画像テスト
        # ======================================

        if text == "画像テスト":

            image_url = (
                request.host_url.rstrip("/")
                + "/images/test.png"
            )

            reply_image(
                reply_token,
                image_url
            )

            continue


        # ======================================
        # オールリセット
        # ======================================

        if text == "オールリセット":

            current_room = "か"
            history = ""

            n_unlocked = False
            delete_unlocked = False
            wa_reached = False
            game_clear = False

            entry_direction = None
            view_direction = "下"

            update_user_state(
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear,
                entry_direction,
                view_direction
            )

            reply_text = (
                "すべての記録をリセットしました。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # 履歴リセット
        # ======================================

        if text == "履歴リセット":

            current_room = "か"
            history = ""

            entry_direction = None
            view_direction = "下"

            update_user_state(
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear,
                entry_direction,
                view_direction
            )

            reply_text = (
                "履歴をリセットしました。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # 振り向く
        # ======================================

        if text == "振り向く":

            # 最初の部屋など、
            # まだ入室方向がない場合
            if entry_direction is None:

                reply_text = (
                    "今は振り向くことができません。"
                )

                send_text_reply(
                    reply_token,
                    reply_text
                )

                continue


            # 現在の視点を180度反転
            view_direction = opposite_direction[
                view_direction
            ]


            update_user_state(
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear,
                entry_direction,
                view_direction
            )


            image_url = get_room_image_url(
                current_room,
                view_direction
            )


            if image_url:

                reply_image(
                    reply_token,
                    image_url
                )

            else:

                reply_text = (
                    "振り向きました。"
                )

                send_text_reply(
                    reply_token,
                    reply_text
                )

            continue


        # ======================================
        # 状態確認
        # ======================================

        if text == "状態確認":

            if user_id != ADMIN_USER_ID:

                reply_text = (
                    "このコマンドは使用できません。"
                )

            else:

                history_display = (
                    " → ".join(history.split(","))
                    if history
                    else "なし"
                )

                entry_display = (
                    entry_direction
                    if entry_direction
                    else "なし"
                )

                view_display = (
                    view_direction
                    if view_direction
                    else "なし"
                )

                reply_text = (
                    "【現在の状態】\n"
                    f"現在地：{current_room}\n"
                    f"入室方向：{entry_display}\n"
                    f"現在の視点：{view_display}\n"
                    f"入力履歴：{history_display}\n"
                    f"な解放：{'ON' if n_unlocked else 'OFF'}\n"
                    f"削除部屋：{'ON' if delete_unlocked else 'OFF'}\n"
                    f"わ到達：{'ON' if wa_reached else 'OFF'}\n"
                    f"ゲームクリア：{'ON' if game_clear else 'OFF'}"
                )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # ゲームクリア済み
        # ======================================

        if game_clear:

            reply_text = (
                "このゲームはすでにクリアしています！\n"
                "もう一度遊ぶ場合は「オールリセット」と入力してください。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # 移動入力を取得
        # ======================================

        direction = room_inputs.get(
            current_room,
            {}
        ).get(text)


        # ======================================
        # 移動入力ではない
        # ======================================

        if direction is None:

            reply_text = (
                f"「{text}」では移動できません。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # 移動先
        # ======================================

        next_room = rooms[current_room].get(direction)


        # ======================================
        # 扉が存在しない
        # ======================================

        if next_room is None:

            reply_text = (
                "その方向には進めません。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # 削除部屋
        # ======================================

        if next_room == "DELETE":

            if not delete_unlocked:

                reply_text = (
                    "その扉はまだ開いていません。"
                )

                send_text_reply(
                    reply_token,
                    reply_text
                )

                continue


            current_room = "か"
            history = ""

            entry_direction = None
            view_direction = "下"

            update_user_state(
                user_id,
                current_room,
                history,
                n_unlocked,
                delete_unlocked,
                wa_reached,
                game_clear,
                entry_direction,
                view_direction
            )

            reply_text = (
                "履歴をリセットしました。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # なへの移動
        # ======================================

        if next_room == "な" and not n_unlocked:

            reply_text = (
                "その扉はまだロックされています。"
            )

            send_text_reply(
                reply_token,
                reply_text
            )

            continue


        # ======================================
        # 実際に移動
        # ======================================

        previous_room = current_room

        current_room = next_room


        # --------------------------------------
        # 移動履歴
        # --------------------------------------

        if history:

            history += "," + text

        else:

            history = text


# --------------------------------------
# プレイヤー視点での移動方向
# --------------------------------------

        relative_direction = get_relative_direction(
            view_direction,
            direction
        )


        # --------------------------------------
        # 新しい部屋に入ったときの向き
        #
        # 例：
        # か → な
        #
        # 「か」から「な」へ右に進んだ場合、
        # なでは左側に入ってきた扉がある。
        #
        # したがって、
        # entry_direction = 左
        # view_direction  = 右
        # --------------------------------------

        entry_direction = opposite_direction[direction]

        view_direction = direction


        # ======================================
        # わの部屋
        # ======================================

        if current_room == "わ":

            # ----------------------------------
            # ゲームクリア
            # ----------------------------------

            if history == "こ,の,よ":

                game_clear = True

                update_user_state(
                    user_id,
                    current_room,
                    history,
                    n_unlocked,
                    delete_unlocked,
                    wa_reached,
                    game_clear,
                    entry_direction,
                    view_direction
                )

                reply_text = (
                    "🎉 ゲームクリア！ 🎉\n\n"
                    "おめでとうございます！"
                )

                send_text_reply(
                    reply_token,
                    reply_text
                )

                continue


            # ----------------------------------
            # 初回到達
            # ----------------------------------

            if not wa_reached:

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
                    game_clear,
                    entry_direction,
                    view_direction
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
                            "originalContentUrl":
                                base_url + "/images/wa_" +
                                {
                                    "上": "up",
                                    "下": "down",
                                    "左": "left",
                                    "右": "right"
                                }[view_direction] + ".png",
                            "previewImageUrl":
                                base_url + "/images/wa_" +
                                {
                                    "上": "up",
                                    "下": "down",
                                    "左": "left",
                                    "右": "right"
                                }[view_direction] + ".png"
                        },
                        {
                            "type": "image",
                            "originalContentUrl":
                                base_url + "/images/final.png",
                            "previewImageUrl":
                                base_url + "/images/final.png"
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


            # ----------------------------------
            # 2回目以降のわ
            # ----------------------------------

            else:

                update_user_state(
                    user_id,
                    current_room,
                    history,
                    n_unlocked,
                    delete_unlocked,
                    wa_reached,
                    game_clear,
                    entry_direction,
                    view_direction
                )


                answer_text = "".join(
                    history.split(",")
                )


                base_url = request.host_url.rstrip("/")


                direction_names = {
                    "上": "up",
                    "下": "down",
                    "左": "left",
                    "右": "right"
                }


                image_url = (
                    base_url
                    + "/images/wa_"
                    + direction_names[view_direction]
                    + ".png"
                )


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
                        },
                        {
                            "type": "image",
                            "originalContentUrl":
                                base_url + "/images/final.png",
                            "previewImageUrl":
                                base_url + "/images/final.png"
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


        # ======================================
        # 通常の部屋
        # ======================================

        update_user_state(
            user_id,
            current_room,
            history,
            n_unlocked,
            delete_unlocked,
            wa_reached,
            game_clear,
            entry_direction,
            view_direction
        )


        # --------------------------------------
        # 画像が存在する場合は画像を表示
        # --------------------------------------

        image_url = get_room_image_url(
            current_room,
            view_direction
        )


        if image_url:

            reply_image(
                reply_token,
                image_url,
                f"{relative_direction}方向の部屋に移動しました。"
            )

        else:

            reply_text = (
                f"{current_room}の部屋に移動しました！"
            )

            send_text_reply(
                reply_token,
                reply_text
            )


    return "OK", 200


# ==========================================
# テキスト返信
# ==========================================

def send_text_reply(reply_token, reply_text):

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

    print(
        "LINEへの返信結果:",
        response.status_code
    )

    print(response.text)


# ==========================================
# 起動時DB初期化
# ==========================================

initialize_database()
