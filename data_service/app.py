from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/info", methods=["GET"])
def data_info():
    return jsonify({
        "message": "Secure data access successful!",
        "items": [1, 2, 3, 4]
    })

if __name__ == "__main__":
    app.run(port=5002)
