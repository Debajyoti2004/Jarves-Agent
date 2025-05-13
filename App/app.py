from flask import Flask, render_template, Response, request, jsonify
import time
import queue
import logging
import json
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
flask_logger = logging.getLogger("FlaskUI")

message_queue = queue.Queue()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ui_event', methods=['POST'])
def handle_ui_event():
    data = request.json
    event_type = data.get("event")
    text_content = data.get("text")
    flask_logger.info(f"UI Event Received: {event_type}, Text Snippet: {str(text_content)[:70] if text_content else 'N/A'}...")
    message_to_send = {"event": event_type}
    if text_content is not None:
        message_to_send["text"] = str(text_content)
    message_queue.put(f"data: {json.dumps(message_to_send)}\n\n")
    return jsonify({"status": "event_received", "event": event_type}), 200

@app.route('/listen_events')
def listen_events():
    def event_stream():
        flask_logger.info("New SSE client connected to /listen_events.")
        try:
            while True:
                try:
                    message = message_queue.get(timeout=25)
                    yield message
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            flask_logger.info("SSE client disconnected from /listen_events.")
        except Exception as e:
            flask_logger.error(f"Error in SSE event_stream: {e}", exc_info=True)
        finally:
            flask_logger.info("Closing event_stream for a client.")
    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    flask_logger.info("Starting Flask UI server on http://127.0.0.1:5000")
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)