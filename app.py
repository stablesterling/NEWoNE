import os
from flask import Flask, request, jsonify, send_from_directory
import requests
from flask_cors import CORS

# We set template_folder and static_folder to current directory '.'
app = Flask(__name__, static_folder='.', template_folder='.')
CORS(app)

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

@app.route('/')
def index():
    # Serves the index.html file from the root
    return send_from_directory('.', 'index.html')

@app.route('/api/search')
def search():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "No query provided"}), 400

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'maxResults': 12,
        'key': YOUTUBE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
