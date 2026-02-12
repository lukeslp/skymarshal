from flask import Flask
from flask_socketio import SocketIO
import eventlet
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import websocket  # websocket-client
import httpx  # sync mode

eventlet.monkey_patch()  # Patch standard libraries for eventlet
app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet")

# Sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

def listen_to_firehose():
    ws = websocket.WebSocket()
    ws.connect("wss://firehose.example.com")
    while True:
        data = ws.recv()
        sentiment = analyzer.polarity_scores(data)
        socketio.emit("update", {"data": data, "sentiment": sentiment})

@socketio.on("connect")
def handle_connect():
    eventlet.spawn(listen_to_firehose)  # Greenlet for WebSocket

if __name__ == "__main__":
    socketio.run(app, port=5000)
