from flask import Flask
app = Flask(__name__)

@app.route('/')
def check_up():
    return 'Mkv-TBot Running!'

if __name__ == "__main__":
    app.run()
