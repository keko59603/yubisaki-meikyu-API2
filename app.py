from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return "Yubisaki no Meikyu API is alive!"

@app.route("/callback", methods=["POST"])
def callback():
    print("LINEからWebhookを受信しました！")
    print(request.get_json())
    return "OK", 200
