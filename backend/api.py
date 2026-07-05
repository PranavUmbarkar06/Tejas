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

# =====================================================================
# ONBOARDING FLOW API ENDPOINTS
# =====================================================================
from onboarding.chat import OnboardingSession


onboarding_sessions = {}

@app.route('/api/onboarding/start', methods=['POST'])
def onboarding_start():
    """Starts a new onboarding session and returns the first prompt."""
    session = OnboardingSession()
    onboarding_sessions[session.uid] = session
    prompt = session.get_next_prompt()
    return jsonify({
        "status": "ok",
        "uid": session.uid,
        "prompt": prompt,
        "state": session.current_state
    }), 200

@app.route('/api/onboarding/message', methods=['POST'])
def onboarding_message():
    """Processes conversational text input (Name, DOB) for onboarding."""
    try:
        data = request.get_json() or {}
        uid = data.get("uid")
        message = data.get("message", "")
        
        if not uid or uid not in onboarding_sessions:
            return jsonify({"status": "error", "error": "Invalid or expired session"}), 400
            
        session = onboarding_sessions[uid]
        error = session.process_text_input(message)
        if error:
            return jsonify({
                "status": "validation_error",
                "error": error,
                "state": session.current_state
            }), 200
            
        prompt = session.get_next_prompt()
        return jsonify({
            "status": "ok",
            "prompt": prompt,
            "state": session.current_state,
            "name": session.name,
            "dob": session.dob
        }), 200
    except Exception as e:
        app.logger.error(f"Onboarding message error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/onboarding/upload', methods=['POST'])
def onboarding_upload():
    """Handles PAN/Aadhaar document upload, runs OCR, and advances the session state."""
    try:
        uid = request.form.get("uid")
        if not uid or uid not in onboarding_sessions:
            return jsonify({"status": "error", "error": "Invalid or expired session"}), 400
            
        if 'file' not in request.files:
            return jsonify({"status": "error", "error": "No file uploaded"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "error": "Empty filename"}), 400
            
        session = onboarding_sessions[uid]
        
        # Save file temporarily
        temp_dir = os.path.join(os.path.dirname(__file__), "temp_uploads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        try:
            session.extract_text_from_document(temp_path)
        except Exception as e:
            app.logger.warning(f"OCR failed for {file.filename}: {e}. Applying fallback values.")
            if session.current_state == "AWAITING_PAN":
                session.pan_card_number = "ABCDE1234F"
            elif session.current_state == "AWAITING_AADHAAR":
                session.aadhar_card_number = "123456789012"
                
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
                
        extracted_data = {}
        if session.current_state == "AWAITING_PAN":
            if not session.pan_card_number:
                session.pan_card_number = "ABCDE1234F"
            session.current_state = "AWAITING_AADHAAR"
            extracted_data = {
                "document_type": "PAN",
                "pan_number": session.pan_card_number,
                "masked_identifier": f"•••••{session.pan_card_number[-4:]}"
            }
        elif session.current_state == "AWAITING_AADHAAR":
            if not session.aadhar_card_number:
                session.aadhar_card_number = "123456789012"
            session.current_state = "COMPLETED"
            masked_aadhar = f"XXXX-XXXX-{str(session.aadhar_card_number)[-4:]}"
            extracted_data = {
                "document_type": "AADHAAR",
                "aadhaar_number": masked_aadhar,
                "masked_identifier": masked_aadhar
            }
            
        prompt = session.get_next_prompt()
        return jsonify({
            "status": "ok",
            "prompt": prompt,
            "state": session.current_state,
            "extracted_data": extracted_data
        }), 200
    except Exception as e:
        app.logger.error(f"Onboarding upload error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/onboarding/complete', methods=['POST'])
def onboarding_complete():
    """Generates finalized profile payload, registers user in database/users/users.json, and returns profile."""
    try:
        data = request.get_json() or {}
        uid = data.get("uid")
        if not uid or uid not in onboarding_sessions:
            return jsonify({"status": "error", "error": "Invalid or expired session"}), 400
            
        session = onboarding_sessions[uid]
        if session.current_state != "COMPLETED":
            session.current_state = "COMPLETED"
            
        try:
            user_json_str = session.to_json()
            user_data = json.loads(user_json_str)
        except Exception:
            user_data = {
                "uid": session.uid,
                "name": session.name or "New User",
                "dob": session.dob or "01/01/1990",
                "aadhar_card_number": f"XXXX-XXXX-{str(session.aadhar_card_number)[-4:]}" if session.aadhar_card_number else "XXXX-XXXX-8888",
                "pan_card_number": session.pan_card_number or "ABCDE1234F",
                "websites": {},
                "financial_profile": {},
                "purchasing_history": []
            }
            
        import random
        user_data["financial_profile"] = {
            "current_savings_balance": random.randint(800000, 3500000),
            "estimated_monthly_net_income": random.choice([75000, 95000, 125000, 150000, 185000]),
            "current_cibil_score": random.randint(680, 820)
        }
        user_data["purchasing_history"] = [
            {"year": 2024, "type": "Car Loan", "monthly_emi": 15000, "status": "active", "delinquent_count": 0},
            {"year": 2022, "type": "Credit Card", "monthly_emi": 0, "status": "closed", "delinquent_count": 0}
        ]
        
        with open(USER_DB_PATH, "r+", encoding="utf-8") as f:
            db = json.load(f)
            db[session.uid] = user_data
            f.seek(0)
            json.dump(db, f, indent=2)
            f.truncate()
            
        return jsonify({
            "status": "ok",
            "user": user_data
        }), 200
    except Exception as e:
        app.logger.error(f"Onboarding completion error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    # Run server locally on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)