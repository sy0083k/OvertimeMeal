from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello from Overtime Meal App!"

if __name__ == '__main__':
    app.run() 