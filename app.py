from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Yubisaki no Meikyu API is alive!"

if __name__ == "__main__":
    app.run()
