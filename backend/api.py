import os
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import your actual orchestrator logic directly
from orchestrator import handle_user_request, load_user_profile_context

app = Flask(__name__)

# Enable CORS safely across all API endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Define the relative database path to match your layout
USER_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../database/users/users.json"))

@app.route('/api/user/<uid>', methods=['GET'])
def get_user_profile(uid):
    """
    Fetches the profile context block for screen initialization using your 
    existing structural load function.
    """
    result = load_user_profile_context(uid, db_path=USER_DB_PATH)
    
    if result.get("error") is None and result.get("profile") is not None:
        return jsonify({
            'status': 'ok',
            'user': result["profile"]
        }), 200
    else:
        logger_msg = result.get("error", "unknown_profile_error")
        app.logger.warning(f"Profile fetch failed for UID {uid}: {logger_msg}")
        return jsonify({
            'status': 'error',
            'error': 'Server error or servers are down'
        }), 500


@app.route('/api/request', methods=['POST'])
def process_request():
    """
    Routes incoming prompts through your Gemini intent orchestration pipeline.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'Server error or servers are down'}), 400
            
        uid = data.get('uid')
        prompt = data.get('prompt')

        if not uid or not prompt:
            return jsonify({'status': 'error', 'error': 'Server error or servers are down'}), 400

        # FIX: Align positional arguments perfectly with your orchestrator signature:
        # handle_user_request(raw_user_input, uid, user_db_path, chroma_db_path)
        output_envelope = handle_user_request(
            raw_user_input=prompt,
            uid=uid,
            user_db_path=USER_DB_PATH
        )
        
        # Translate orchestrator status variants directly to your frontend status expectations
        if output_envelope and output_envelope.get('status') in ['ok', 'needs_clarification']:
            return jsonify({
                'intent': output_envelope.get('intent'),
                'status': 'ok', # Keeps frontend parsing running normally
                'message': output_envelope.get('message')
            }), 200
        else:
            return jsonify({'status': 'error', 'error': 'Server error or servers are down'}), 500
            
    except Exception as e:
        app.logger.error(f"Orchestration route exception encountered: {str(e)}")
        return jsonify({'status': 'error', 'error': 'Server error or servers are down'}), 500

if __name__ == '__main__':
    # Run server locally on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)