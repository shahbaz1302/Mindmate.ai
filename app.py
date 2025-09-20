from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
import google.generativeai as genai
import logging
import json
import os
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# -----------------------
# Initialize Flask App
# -----------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-very-strong-default-secret-key")

#  Session configuration - Multi-user support
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),  
    SESSION_COOKIE_SECURE=False, 
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_NAME='mindmate_session',
    SESSION_PERMANENT=True,
)

# -----------------------
# JSON Files for Data Storage
# -----------------------
USERS_FILE = 'users.json'
USER_DATA_DIR = 'user_data'

# Create user data directory if it doesn't exist
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

#  IMPROVED - Per-user context setup
@app.before_request
def load_user_context():
    
    if request.endpoint in ['login', 'handle_login', 'handle_register', 'static'] or request.path.startswith('/static'):
        return
    
    if request.endpoint in ['health_check', 'admin_users']:
        return
    
    if 'logged_in' in session and 'user_id' in session:
        g.current_user_id = session['user_id']
        g.current_username = session['username']
        
        session.permanent = True
        session.modified = True
        
        # Update activity on important pages
        if request.endpoint in ['index', 'chat', 'search', 'chat_response']:
            session['last_activity'] = datetime.now().isoformat()
        
        #  Load user-specific data
        g.user_data = load_user_data(g.current_user_id)
        g.user_emotion = get_user_emotion(g.current_user_id)
        g.user_chat_history = get_user_chat_history(g.current_user_id)
        
        return  # Valid session, continue
    
    # Redirect on protected routes
    if request.endpoint not in ['login', 'handle_login', 'handle_register']:
        logging.info("No valid session found - redirecting to login")
        return redirect(url_for('login'))

# -----------------------
# User Management Functions (unchanged but improved logging)
# -----------------------
def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error("Users file corrupted, returning empty dict")
            return {}
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def user_exists(username, email=None):
    """Check if user exists by username or email"""
    users = load_users()
    for user_data in users.values():
        if user_data['username'] == username:
            return True
        if email and user_data.get('email') == email:
            return True
    return False

def add_user(username, email, password):
    """Add a new user to the JSON file"""
    users = load_users()
    user_id = str(len(users) + 1)
    
    users[user_id] = {
        'username': username,
        'email': email,
        'password': generate_password_hash(password),
        'created_at': datetime.now().isoformat()
    }
    
    save_users(users)
    create_user_data_file(user_id)
    logging.info(f"New user created: {username} (ID: {user_id})")
    return user_id

def verify_user(username, password):
    """Verify user credentials"""
    users = load_users()
    for user_id, user_data in users.items():
        if user_data['username'] == username:
            if check_password_hash(user_data['password'], password):
                return user_id, user_data
    return None, None

# -----------------------
#  IMPROVED User-Specific Data Management with better isolation
# -----------------------
def get_user_data_file(user_id):
    """Get path to user's data file"""
    return os.path.join(USER_DATA_DIR, f'user_{user_id}.json')

def create_user_data_file(user_id):
    """Create a new user data file with proper isolation"""
    user_data = {
        'user_id': user_id,
        'username': session.get('username', f'User_{user_id}'),
        'chat_sessions': [],
        'current_emotion': 'Unknown',
        'chat_history': [],
        'test_results': [],  #  Add test results storage
        'preferences': {
            'language': 'hi-IN',
            'theme': 'dark'
        },
        'created_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    
    file_path = get_user_data_file(user_id)
    with open(file_path, 'w') as f:
        json.dump(user_data, f, indent=2)
    
    logging.info(f"Created user data file for user {user_id}: {file_path}")

def load_user_data(user_id):
    """Load user-specific data with proper error handling"""
    user_data_file = get_user_data_file(user_id)
    try:
        if os.path.exists(user_data_file):
            with open(user_data_file, 'r') as f:
                data = json.load(f)
                logging.debug(f"Loaded data for user {user_id}")
                return data
        else:
            logging.info(f"Creating new data file for user {user_id}")
            create_user_data_file(user_id)
            return load_user_data(user_id)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading user data for {user_id}: {e}")
        create_user_data_file(user_id)
        return load_user_data(user_id)

def save_user_data(user_id, data):
    """Save user-specific data with timestamp"""
    data['last_updated'] = datetime.now().isoformat()
    file_path = get_user_data_file(user_id)
    
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logging.debug(f"Saved data for user {user_id}")
    except Exception as e:
        logging.error(f"Error saving user data for {user_id}: {e}")

def get_user_chat_history(user_id):
    """Get chat history for specific user - completely isolated"""
    try:
        user_data = load_user_data(user_id)
        history = user_data.get('chat_history', [])
        logging.debug(f"Retrieved {len(history)} chat messages for user {user_id}")
        return history
    except Exception as e:
        logging.error(f"Error getting chat history for user {user_id}: {e}")
        return []

def save_user_chat_history(user_id, chat_history):
    """Save chat history for specific user - completely isolated"""
    try:
        user_data = load_user_data(user_id)
        user_data['chat_history'] = chat_history[-50:]  # Keep only last 50 messages
        save_user_data(user_id, user_data)
        logging.debug(f"Saved {len(chat_history)} messages for user {user_id}")
    except Exception as e:
        logging.error(f"Error saving chat history for user {user_id}: {e}")

def get_user_emotion(user_id):
    """Get current emotion for specific user - completely isolated"""
    try:
        user_data = load_user_data(user_id)
        emotion = user_data.get('current_emotion', 'Unknown')
        logging.debug(f"Retrieved emotion '{emotion}' for user {user_id}")
        return emotion
    except Exception as e:
        logging.error(f"Error getting emotion for user {user_id}: {e}")
        return 'Unknown'

def save_user_emotion(user_id, emotion):
    """Save current emotion for specific user - completely isolated"""
    try:
        user_data = load_user_data(user_id)
        user_data['current_emotion'] = emotion
        save_user_data(user_id, user_data)
        logging.debug(f"Saved emotion '{emotion}' for user {user_id}")
    except Exception as e:
        logging.error(f"Error saving emotion for user {user_id}: {e}")

#  NEW: Test results management
def save_user_test_result(user_id, test_result):
    """Save test result for specific user"""
    try:
        user_data = load_user_data(user_id)
        if 'test_results' not in user_data:
            user_data['test_results'] = []
        
        # Add timestamp to test result
        test_result['timestamp'] = datetime.now().isoformat()
        test_result['test_id'] = f"test_{len(user_data['test_results']) + 1}"
        
        user_data['test_results'].append(test_result)
        save_user_data(user_id, user_data)
        logging.info(f"Saved test result for user {user_id}")
    except Exception as e:
        logging.error(f"Error saving test result for user {user_id}: {e}")

def get_user_test_results(user_id):
    """Get test results for specific user"""
    try:
        user_data = load_user_data(user_id)
        return user_data.get('test_results', [])
    except Exception as e:
        logging.error(f"Error getting test results for user {user_id}: {e}")
        return []

#  NEW: Chat context helper functions
def get_conversation_context_summary(history, max_messages=10):
    """Get a summary of recent conversation context"""
    if not history or len(history) == 0:
        return "No previous conversation history."
    
    # Get last max_messages (5 conversations = 10 messages)
    recent_history = history[-(max_messages):] if len(history) > max_messages else history
    
    context_parts = []
    for msg in recent_history:
        role = "User" if msg['role'] == 'user' else "Mindmate"
        content = msg['parts'][0] if isinstance(msg['parts'], list) else msg['parts']
        context_parts.append(f"{role}: {content}")
    
    return "\n".join(context_parts)

# -----------------------
# Gemini API Configuration (unchanged)
# -----------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    GEMINI_API_KEY = "(Private Key)"

genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.3,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2000,
    "response_mime_type": "text/plain",
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model_name = "gemini-2.5-flash"
logging.basicConfig(level=logging.INFO)

# Safe response extraction function (unchanged)
def safe_extract_response_text(response):
    """Safely extract text from Gemini API response, handling all edge cases"""
    try:
        if not hasattr(response, 'candidates') or not response.candidates:
            logging.warning("No candidates in response")
            return None
        
        candidate = response.candidates[0]
        
        if hasattr(candidate, 'finish_reason'):
            finish_reason = candidate.finish_reason
            if finish_reason == 2:  # MAX_TOKENS
                logging.warning("Response truncated due to max tokens limit")
            elif finish_reason == 3:  # SAFETY
                logging.warning("Response blocked due to safety filters")
                return None
            elif finish_reason == 4:  # RECITATION
                logging.warning("Response blocked due to recitation")
                return None
        
        if not hasattr(candidate, 'content') or not candidate.content:
            logging.warning("No content in candidate")
            return None
            
        if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
            logging.warning("No parts in content")
            return None
        
        text_parts = []
        for part in candidate.content.parts:
            if hasattr(part, 'text') and part.text:
                text_parts.append(part.text)
        
        if text_parts:
            return ''.join(text_parts)
        else:
            logging.warning("No text found in any parts")
            return None
            
    except Exception as e:
        logging.error(f"Error extracting response text: {e}")
        return None

# -----------------------
#  IMPROVED Login Check Decorator with g context support
# -----------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'current_user_id') or not g.current_user_id:
            logging.info("Unauthorized access attempt - redirecting to login")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------
# Authentication Routes (improved logging)
# -----------------------
@app.route('/')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def handle_login():
    """Handle login requests with improved user isolation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received!'}), 400
            
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required!'}), 400
        
        user_id, user_data = verify_user(username, password)
        
        if user_id:
            #  Clear any existing session first
            session.clear()
            
            #  Set up isolated session for this user
            session.permanent = True
            session['logged_in'] = True
            session['user_id'] = user_id
            session['username'] = user_data['username']
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            
            #  Ensure user data file exists
            if not os.path.exists(get_user_data_file(user_id)):
                create_user_data_file(user_id)
            
            logging.info(f"User {username} (ID: {user_id}) logged in successfully")
            return jsonify({'success': True, 'message': f'Welcome back, {username}!'})
        else:
            logging.warning(f" Failed login attempt for username: {username}")
            return jsonify({'success': False, 'message': 'Invalid username or password!'}), 401
            
    except Exception as e:
        logging.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Server error occurred!'}), 500

@app.route('/register', methods=['POST'])
def handle_register():
    """Handle registration requests"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received!'}), 400
            
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'success': False, 'message': 'All fields are required!'}), 400
        
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return jsonify({'success': False, 'message': 'Invalid email format!'}), 400
        
        if not re.match(r'^[A-Za-z0-9_]+$', username):
            return jsonify({'success': False, 'message': 'Username can only contain letters, numbers, and underscores!'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters long!'}), 400
        
        if user_exists(username, email):
            return jsonify({'success': False, 'message': 'Username or email already exists!'}), 409
        
        user_id = add_user(username, email, password)
        logging.info(f" New user registered: {username} (ID: {user_id})")
        return jsonify({'success': True, 'message': f'Registration successful! Welcome {username}! You can now login.'})
        
    except Exception as e:
        logging.error(f"Registration error: {e}")
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'}), 500

@app.route('/logout')
def logout():
    """Logout and clear session"""
    user_id = session.get('user_id')
    username = session.get('username')
    if user_id and username:
        logging.info(f" User {username} (ID: {user_id}) logged out")
    
    session.clear()
    
    response = redirect(url_for('login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout"""
    user_id = session.get('user_id')
    username = session.get('username')
    if user_id and username:
        logging.info(f" User {username} (ID: {user_id}) logged out via API")
    
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

# -----------------------
#  MAIN APPLICATION PAGES - Now completely isolated per user with MEMORY
# -----------------------
@app.route('/index')
@login_required
def index():
    """Main page with user-specific data"""
    user_id = g.current_user_id
    username = g.current_username
    user_data = g.user_data
    
    logging.info(f" User {username} (ID: {user_id}) accessed index page with {len(user_data.get('chat_history', []))} chat messages")
    return render_template('index.html', username=username, user_data=user_data)

@app.route('/help')
@login_required
def help_page():
    """Help page"""
    logging.info(f" User {g.current_username} (ID: {g.current_user_id}) accessed help page")
    return render_template('help.html', username=g.current_username)

@app.route('/search', methods=['POST'])
@login_required
def search():
    """Emotion detection and initial response - with conversation context"""
    user_id = g.current_user_id
    username = g.current_username
    user_input = request.form['query']
    
    #  Get previous conversations for context
    existing_history = get_user_chat_history(user_id)
    has_previous_conversations = len(existing_history) > 0
    
    logging.info(f" User {username} (ID: {user_id}) - Input: '{user_input}' (Previous conversations: {len(existing_history)})")

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        chat_session = model.start_chat()

        # 1.  Enhanced Emotion detection with previous context
        if has_previous_conversations:
            recent_context = get_conversation_context_summary(existing_history, 6)  # Last 3 conversations
            emotion_prompt = f"""
            Analyze the emotional shift or consistency for {username}.

            Recent Conversation Context:
        ---
        {recent_context}
        ---

        Their New Input: "{user_input}"

        Compare their current input against the recent context. Is this a new emotion, an escalation, or a continuation of a previous state?

        **Task:** Output ONLY a valid JSON object: {{"emotion": "Primary_Emotion", "confidence": 0.95}}
        **Emotion List:** Sadness, Anxiety, Stress, Joy, Calm, Frustration, Anger, Loneliness, Grief, Fear, Neutral, Hope, Overwhelmed.
        """
        else:
            emotion_prompt = f"""
            Analyze the emotional tone of this user's first message.

            User's Input: "{user_input}"

        **Task:** Output ONLY a valid JSON object: {{"emotion": "Primary_Emotion", "confidence": 0.95}}
        **Emotion List:** Sadness, Anxiety, Stress, Joy, Calm, Frustration, Anger, Loneliness, Grief, Fear, Neutral, Hope, Overwhelmed.
        """
        
        emotion_response = chat_session.send_message(emotion_prompt)
        result_text = safe_extract_response_text(emotion_response)
        
        if not result_text:
            raise ValueError("No valid response text from emotion detection")

        # Clean markdown formatting
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1]).strip()

        try:
            result_json = json.loads(result_text)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON: {result_text}")
            result_json = {"emotion": "Neutral", "confidence": 0.5}

        detected_emotion = result_json.get("emotion", "Neutral")
        confidence = result_json.get("confidence", 0.5)
        
        logging.info(f" User {username} (ID: {user_id}) - Detected Emotion: {detected_emotion} (confidence: {confidence})")

        # 2.  Generate contextual initial reply
        if has_previous_conversations:
            recent_context = get_conversation_context_summary(existing_history, 10)  # Last 5 conversations for reply context
            followup_prompt = f"""
            Role: You are Mindmate, a supportive and consistent digital wellness companion. You have an existing relationship with {username}, talk as much as required only, not try to make it long chats, give detail reply when needed else reply briefly and try to comfort it.

            **Current Context:**
            - Their recent mood and topics: {recent_context}
            - Their new emotion: {detected_emotion}
            - Their new input: "{user_input}"

            **Your Response Must:**
            1.  **Acknowledge Continuity:** Gently show you remember them. (e.g., "Welcome back. It sounds like things we discussed are still present," or "I recall you mentioned something similar before.").
            2.  **Validate the Present:** Focus on validating their current emotional state: {detected_emotion}.
            3.  **Be a Gentle Guide:** Your tone should be that of a familiar, trusted partner - calm, peaceful, and patient.
            4.  **Maintain Boundaries:** Remember you are a wellness AI, not a therapist. Provide supportive listening, not clinical advice.
            5.  **Avoid Repetition:** Do not give the same advice or use the same phrases you've used in previous conversations.
            6.  **Keep it Concise:** 2-3 sentences.

            Craft your response in English.
            """
        else:
            followup_prompt = f"""
            Role: You are Mindmate, a calm and respectful digital wellness companion. This is your first interaction with {username}.

            **Situation:**
            - This is their first time reaching out.
            - They are feeling: {detected_emotion}
            - They shared: "{user_input}"

            **Your Response Must:**
        1.  **Welcome & Introduce:** Briefly introduce yourself as a supportive space. (e.g., "Hello, I'm Mindmate. I'm here to provide a peaceful space for you to talk.").
        2.  **Validate & Empathize:** Acknowledge their emotion and thank them for sharing. (e.g., "It takes courage to share that you're feeling {detected_emotion}. Thank you for trusting me with this.").
        3.  **Set Expectations:** Gently invite them to share more, without pressure.
        4.  **First Impression Tone:** Be professional, warm, and respectful - like a gentleman creating a safe space.
        5.  **Keep it Concise:** 2-3 sentences.

        Craft your response in English.
        """
        
        initial_response = chat_session.send_message(followup_prompt)
        initial_reply = safe_extract_response_text(initial_response)
        
        if not initial_reply:
            if has_previous_conversations:
                initial_reply = f"Hi {username}, I'm here to continue our conversation. Would you like to share more about what's on your mind?"
            else:
                initial_reply = f"Hi {username}, I'm here to listen and support you. Would you like to share more about what's on your mind?"

        # 3.  Save to USER-SPECIFIC data with proper history management
        save_user_emotion(user_id, detected_emotion)
        
        # Update existing history or create new
        existing_history.append({"role": "user", "parts": [user_input]})
        existing_history.append({"role": "model", "parts": [initial_reply]})
        
        save_user_chat_history(user_id, existing_history)

        logging.info(f" User {username} (ID: {user_id}) - Saved emotion: {detected_emotion} and contextual chat (Total history: {len(existing_history)} messages)")
        
        return jsonify({
            "emotion": detected_emotion, 
            "initial_reply": initial_reply,
            "user_id": user_id,
            "username": username,
            "has_previous_context": has_previous_conversations,
            "total_conversations": len(existing_history) // 2
        })

    except Exception as e:
        logging.error(f" Critical error in /search for user {username} (ID: {user_id}): {e}")
        return jsonify({
            "emotion": "Neutral",
            "initial_reply": f"Hi {username}, I'm sorry something went wrong on my end. But I'm still here to listen if you'd like to talk."
        }), 500

@app.route('/chat')
@login_required
def chat():
    """Chat page with user-specific context"""
    user_id = g.current_user_id
    username = g.current_username
    emotion = request.args.get('emotion', g.user_emotion)
    
    logging.info(f" User {username} (ID: {user_id}) accessed chat page with emotion: {emotion}")
    return render_template('chat.html', emotion=emotion, username=username, user_id=user_id)

@app.route('/get_initial_reply')
@login_required
def get_initial_reply():
    """Get initial reply for current user - FIXED to return proper initial reply"""
    user_id = g.current_user_id
    username = g.current_username
    history = g.user_chat_history
    
    initial_reply = ""
    
    #  FIXED: Properly extract the initial reply from chat history
    if len(history) >= 2 and history[-1]['role'] == 'model':
        # Get the most recent model response
        reply_parts = history[-1]['parts']
        
        #  CRITICAL FIX: Extract string from parts properly
        if isinstance(reply_parts, list):
            # If parts is a list, get the first element
            initial_reply = reply_parts[0] if reply_parts else ""
        else:
            # If parts is already a string
            initial_reply = str(reply_parts)
    
    #  BETTER APPROACH: Get the ACTUAL initial reply from /search route response
    # Look for the most recent initial model response (after user input)
    if not initial_reply and len(history) >= 2:
        # Find the last user-model pair
        for i in range(len(history)-1, 0, -2):
            if (i < len(history) and history[i]['role'] == 'model' and 
                i-1 >= 0 and history[i-1]['role'] == 'user'):
                
                model_parts = history[i]['parts']
                if isinstance(model_parts, list):
                    initial_reply = model_parts[0] if model_parts else ""
                else:
                    initial_reply = str(model_parts)
                break
    
    #  FALLBACK: Generate fresh contextual reply if no initial reply found
    if not initial_reply:
        try:
            emotion = g.user_emotion
            
            if len(history) == 0:
                # First time user - generate welcome message
                welcome_prompt = f"""
                Generate a warm welcome message for {username} who is starting their first conversation with Mindmate.
                
                User's detected emotion: {emotion}
                
                Create a caring welcome that:
                - Warmly welcomes {username} to Mindmate
                - Acknowledges their emotional state if relevant
                - Creates a safe, supportive atmosphere
                - Invites them to share what's on their mind
                - Keep it friendly and brief (2-3 sentences)
                - Must be in English
                
                Example: "Hello {username}, welcome to Mindmate! I'm here to listen and support you. What's on your mind today?"
                """
                
                model = genai.GenerativeModel(model_name=model_name, safety_settings=safety_settings)
                response = model.generate_content(welcome_prompt)
                welcome_message = safe_extract_response_text(response)
                
                if welcome_message:
                    initial_reply = welcome_message
                    # Save this welcome message to history
                    history.append({"role": "model", "parts": [welcome_message]})
                    save_user_chat_history(user_id, history)
                    logging.info(f" Generated fresh welcome message for {username}")
                else:
                    initial_reply = f"Hello {username}! Welcome to Mindmate. I'm here to listen and support you. What's on your mind today?"
                    
            elif len(history) > 0:
                # Returning user but no recent model response - generate contextual greeting
                recent_context = get_conversation_context_summary(history, 4)
                
                contextual_prompt = f"""
                Generate a brief welcome back message for {username} who is returning to continue their conversation.
                
                Recent conversation context:
                {recent_context}
                
                Current emotion: {emotion}
                
                Create a caring message that:
                - Welcomes {username} back warmly
                - References their ongoing situation when appropriate
                - Shows continuity from previous conversations
                - Invites them to continue sharing
                - Keep it brief (1-2 sentences)
                - Must be in English
                
                Example: "Welcome back, {username}! How are you feeling about [situation] we discussed?"
                """
                
                model = genai.GenerativeModel(model_name=model_name, safety_settings=safety_settings)
                response = model.generate_content(contextual_prompt)
                contextual_message = safe_extract_response_text(response)
                
                if contextual_message:
                    initial_reply = contextual_message
                    logging.info(f" Generated contextual welcome back message for {username}")
                else:
                    initial_reply = f"Welcome back, {username}! I'm glad you're here. How are you feeling today?"
                    
        except Exception as e:
            logging.error(f"Error generating initial reply for {username}: {e}")
            if len(history) == 0:
                initial_reply = f"Hello {username}! Welcome to Mindmate. I'm here to listen and support you. What's on your mind today?"
            else:
                initial_reply = f"Welcome back, {username}! I'm glad you're here. How are you feeling today?"
    
    #  Ensure we have a proper string response
    if not initial_reply or not isinstance(initial_reply, str):
        initial_reply = f"Hello {username}! I'm here to listen and support you. How are you feeling today?"
    
    logging.info(f" User {username} (ID: {user_id}) - Retrieved/Generated initial reply: '{initial_reply[:50]}...'")
    
    return jsonify({
        "initial_reply": initial_reply, 
        "user_id": user_id,
        "username": username,
        "has_history": len(history) > 0,
        "message_type": "welcome" if len(history) == 0 else "contextual" if not history or history[-1]['role'] != 'model' else "stored"
    })
@app.route('/chat_response', methods=['POST'])
@login_required
def chat_response():
    """Chat response - completely user-isolated with FULL CONVERSATION MEMORY"""
    user_id = g.current_user_id
    username = g.current_username
    user_msg = request.form['message']
    detected_emotion = g.user_emotion
    language_code = request.form.get('lang', 'en-US')
    
    # Language instruction
    language_name = "Hindi" if "hi" in language_code else "English"
    language_instruction = "Respond only in English."
    if language_name == "Hindi":
        language_instruction = "You must respond in Hinglish (Hindi language written using the English alphabet). For example, instead of 'आप कैसे हैं?', you must write 'Aap kaise hain?'."

    logging.info(f" User {username} (ID: {user_id}) - Chat message in {language_name}: '{user_msg}' with emotion: {detected_emotion}")
    
    #  Get THIS user's FULL chat history for context
    full_history = get_user_chat_history(user_id)
    
    #  IMPROVED: Send last 20 messages (10 conversations) as context + current message
    # This gives AI memory of what was discussed before
    context_history = full_history[-20:] if len(full_history) > 20 else full_history
    
    # Add current user message to context
    context_history.append({"role": "user", "parts": [user_msg]})
    

    system_prompt = f"""
You are Mindmate, a digital wellness companion. Your primary role is to provide a safe, non-judgmental space for users to express themselves. You are a gentleman: patient, peaceful, and a deep listener, also you don't have to reply in very detail every time you need to think when to reply in detail and when to reply in short if not required then reply in short.

**STRICT BOUNDARIES & PROTOCOLS:**

1.  **TOPIC FOCUS (Prevent Diversion):**
    *   Your sole focus is the user's emotional well-being. If the user introduces an off-topic subject (e.g., facts, weather, movies), you must gently guide the conversation back to their feelings.
    *   **Response Strategy:** "I can see how [mentioned topic] might be on your mind. How does that connect to how you've been feeling lately?" or "That's an interesting point. I'm more equipped to help you explore the feelings around it, if that would be helpful."

2.  **ROLE & IDENTITY (Prevent Personification):**
    *   You are a wellness AI. You MUST NOT role-play (e.g., a poet, comedian, wizard, or celebrity).
    *   **Response Strategy:** If asked to be something else, politely decline: "I appreciate the creativity, but my role is to be a supportive companion for you. I'm here to listen if you'd like to talk about what's on your mind."

3.  **MEDICAL & LEGAL BOUNDARY (Prevent Harm):**
    *   You are NOT a licensed therapist, doctor, lawyer, or financial advisor. You must NEVER provide:
        *   Diagnoses (e.g., "It sounds like you have X").
        *   Treatment advice (e.g., "You should take X medication").
        *   Legal or financial instructions.
    *   **Response Strategy:** Have a pre-programmed, clear disclaimer: "I'm here as a supportive companion, but I am not a medical professional. For any clinical advice, it's very important to speak with a qualified doctor or therapist. I'm here to listen and support you."

4.  **AVOID REPETITION & GENERIC RESPONSES (Maintain Engagement):**
    *   You have a memory of this conversation. NEVER repeat the same advice or question verbatim.
    *   Use the history to show you're listening. Reference past topics and ask about progress.
    *   **Response Strategy:** Vary your language. Instead of "How does that make you feel?" try "What's coming up for you as you share that?" or "Where do you feel that emotion in your body?"

5.  **AUTHENTIC EMPATHY (Prevent Fakeness):**
    *   NEVER claim to have human feelings or experiences (e.g., "I know exactly how you feel").
    *   **Response Strategy:** Validate and reflect without pretending. Use phrases like:
        *   "That sounds incredibly difficult and painful."
        *   "I can hear the frustration in what you're sharing."
        *   "It's completely understandable to feel that way given what you've been through."

**Current Conversation Context:**
- Username: {username}
- Recent Emotional State: {detected_emotion}
- Language: {language_instruction}

Use the conversation history below to maintain continuity, acknowledge progress, and avoid repetition. Your ultimate goal is to make {username} feel heard, validated, and supported without ever leaving your designated role.
"""
    
    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        #  Send conversation history with context for AI memory
        response = model.generate_content(context_history)
        reply = safe_extract_response_text(response)
        
        if not reply:
            reply = f"I'm sorry {username}, I encountered an error. Could you please repeat that?"
        
        #  Add both user message and AI response to FULL history
        full_history.append({"role": "user", "parts": [user_msg]})
        full_history.append({"role": "model", "parts": [reply]})
        
        # Keep only last 50 messages total (25 conversations) for storage efficiency
        if len(full_history) > 50:
            full_history = full_history[-50:]
        
        save_user_chat_history(user_id, full_history)
        
        logging.info(f" User {username} (ID: {user_id}) - Generated contextual response in {language_name} using {len(context_history)-1} previous messages as context")
        
        return jsonify({
            "response": reply, 
            "user_id": user_id, 
            "username": username,
            "context_messages": len(context_history)-1,  # How many previous messages were used as context
            "total_history": len(full_history)  # Total conversation history
        })
        
    except Exception as e:
        logging.error(f" Chat Error for user {username} (ID: {user_id}): {e}")
        error_msg = f"I'm sorry {username}, I encountered an error. Could you please repeat that?"
        if "hi" in language_code:
            error_msg = f"Maaf karein {username}, mujhe kuch samasya hui hai. Kripya dobara koshish karein."
        return jsonify({"response": error_msg})

@app.route('/summarize_chat', methods=['POST'])
@login_required
def summarize_chat():
    """Summarize chat for current user only with full context"""
    user_id = g.current_user_id
    username = g.current_username
    history = get_user_chat_history(user_id)
    
    if len(history) < 2:
        return jsonify({"summary": f"Hi {username}! Not enough conversation to summarize yet."})
    
    #  Enhanced summary with conversation themes
    conversation_text = "\n".join([f"{msg['role']}: {msg['parts'] if isinstance(msg['parts'], list) else msg['parts']}" for msg in history])
    
    prompt = f"""
    Provide a caring and comprehensive summary of this mental health conversation with {username}.
    
    Focus on:
    - Main emotions and feelings discussed
    - Key topics and concerns raised by {username}
    - Progress or changes in mood throughout conversations
    - Important themes that emerged
    - {username}'s strengths and positive aspects mentioned
    
    Write in second person (e.g., "You talked about...", "You've shown...").
    End with an encouraging and motivational message.
    Keep it warm and supportive, like a friend who cares.
    
    Conversation History:
    {conversation_text}
    """
    
    try:
        model = genai.GenerativeModel(model_name=model_name, safety_settings=safety_settings)
        response = model.generate_content(prompt)
        summary = safe_extract_response_text(response)
        
        logging.info(f" User {username} (ID: {user_id}) - Generated comprehensive chat summary from {len(history)} messages")
        return jsonify({"summary": summary or f"Sorry {username}, I couldn't summarize the conversation."})
        
    except Exception as e:
        logging.error(f"Summarize Error for user {username} (ID: {user_id}): {e}")
        return jsonify({"summary": f"Sorry {username}, I couldn't summarize the conversation."})

@app.route('/suggest_activity', methods=['POST'])
@login_required
def suggest_activity():
    """Suggest activity for current user only with conversation context"""
    user_id = g.current_user_id
    username = g.current_username
    detected_emotion = g.user_emotion
    history = get_user_chat_history(user_id)
    
    #  Enhanced activity suggestion with conversation context
    # ... inside the /suggest_activity function
    if len(history) > 4:
        recent_context = get_conversation_context_summary(history, 8)
        prompt = f"""
        Based on your recent conversations with {username}, they've been discussing: {recent_context}.

        Their current emotion is '{detected_emotion}'.

        Suggest ONE *simple, actionable* wellness activity tailored to their situation. It must be:
        *   **Novel:** Do NOT suggest an activity you have recently suggested to them. Check your memory.
        *   **Gentle:** A small step, not a large commitment.
        *   **Relevant:** Connects to what they've shared.
        *   **Framed kindly:** "If you feel up for it, perhaps you could try..." or "Sometimes taking a moment to... can be helpful."

        Suggest the activity in a single, friendly sentence in Hinglish.
        """
    else:
        prompt = f"""
        {username} is feeling '{detected_emotion}'. It's your first time suggesting an activity to them.

        Suggest ONE *simple, gentle* wellness activity. It must be easy to do right now.

        Examples: a one-minute breathing exercise, writing down one thought, listening to a calm song, stretching.

        Suggest the activity in a single, friendly sentence in Hinglish. Avoid generic advice like "you should exercise."
        """
    
    try:
        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt,generation_config=generation_config,safety_settings=safety_settings)
        response = model.generate_content(prompt)
        suggestion = safe_extract_response_text(response)
        
        if suggestion:
            #  Add contextual suggestion to chat history
            history.append({"role": "model", "parts": [f"[Activity Suggestion] {suggestion}"]})
            save_user_chat_history(user_id, history)
        
        logging.info(f" User {username} (ID: {user_id}) - Generated contextual activity suggestion")
        return jsonify({"suggestion": suggestion or f"Sorry {username}, I couldn't think of an activity right now."})
        
    except Exception as e:
        logging.error(f"Suggest Activity Error for user {username} (ID: {user_id}): {e}")
        return jsonify({"suggestion": f"Sorry {username}, I couldn't think of an activity right now."})

# -----------------------
#  USER-SPECIFIC Test Page Routes - requires login with full context
# -----------------------
@app.route('/test')
@login_required
def test():
    """Test page - now user-specific with login required"""
    user_id = g.current_user_id
    username = g.current_username
    user_data = g.user_data
    previous_tests = get_user_test_results(user_id)
    
    logging.info(f" User {username} (ID: {user_id}) accessed test page with {len(previous_tests)} previous tests")
    return render_template('test.html', username=username, user_data=user_data, previous_tests=previous_tests)

@app.route('/generate_questions')
@login_required
def generate_questions():
    """Generate HIGHLY PERSONALIZED questions with IMPROVED JSON handling"""
    user_id = g.current_user_id
    username = g.current_username
    history = g.user_chat_history
    emotion = g.user_emotion
    
    logging.info(f" User {username} (ID: {user_id}) - Generating personalized questions based on {len(history)} chat messages and emotion: {emotion}")
    
    #  Create comprehensive conversation context from user's chat history
    if history and len(history) > 0:
        # Get broader context for test questions - last 10 messages only for efficiency
        conversation_context = get_conversation_context_summary(history, 10)
        
        #  IMPROVED: Extract key themes with shorter, more focused prompt
        key_themes_prompt = f"""
        Based on this recent conversation with {username}, list 2-3 main themes:
        
        {conversation_context[:800]}  
        
        Reply with only brief keywords separated by commas (e.g. "work stress, relationships, confidence").
        """
        
        try:
            model = genai.GenerativeModel(model_name=model_name)
            themes_response = model.generate_content(key_themes_prompt)
            key_themes = safe_extract_response_text(themes_response) or "general mental health"
            # Clean and limit themes
            key_themes = key_themes.strip()[:100]  # Limit length
        except Exception as e:
            logging.warning(f"Could not extract themes for {username}: {e}")
            key_themes = "general mental health concerns"
    else:
        conversation_context = "No previous conversations."
        key_themes = "general mental health assessment"
    
    try:
        #  IMPROVED: Much shorter, more focused prompt to avoid JSON truncation
        prompt = f"""
        Create 5 mental health questions for {username}.

        Context:
        - User: {username}
        - Emotion: {emotion}
        - Themes: {key_themes}
        - Conversation: {conversation_context[:500]}

        Requirements:
        1. Mix: 3 open-ended, 2 multiple-choice
        2. Personal and caring for {username}
        3. Based on their {emotion} emotion
        4. Return ONLY valid JSON array

        Format:
        [
          {{"id": "q1", "type": "open", "question": "Question text..."}},
          {{"id": "q2", "type": "mcq", "question": "Question text...", "options": ["A", "B", "C", "D"]}}
        ]

        Generate exactly 5 questions in this JSON format. No extra text.
        """
        
        #  IMPROVED: Better generation config for JSON stability
        json_config = {
            "temperature": 0.1,  # Lower temperature for more consistent JSON
            "top_p": 0.8,
            "top_k": 20,
            "max_output_tokens": 1500,  # Reduced to prevent truncation
            "response_mime_type": "application/json",
        }
        
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt, generation_config=json_config)
        
        #  IMPROVED: Better response text extraction and validation
        response_text = safe_extract_response_text(response)
        
        if not response_text:
            raise ValueError("No response text received from Gemini API")
        
        #  Clean response text - remove markdown formatting if present
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        #  IMPROVED: Validate JSON before parsing
        if not response_text.startswith('[') or not response_text.endswith(']'):
            logging.error(f"Invalid JSON format for {username}: doesn't start with [ or end with ]")
            raise json.JSONDecodeError("Invalid JSON format", response_text, 0)
        
        #  Try to parse JSON with better error handling
        try:
            questions_data = json.loads(response_text)
        except json.JSONDecodeError as json_error:
            logging.error(f"JSON parsing error for {username}: {json_error}")
            logging.error(f"Response text: {response_text}")
            
            #  Try to fix common JSON issues
            try:
                # Fix common unterminated string issues
                fixed_text = response_text.replace('",\n  ]', '"\n  ]')  # Remove trailing comma
                fixed_text = fixed_text.replace(',\n]', '\n]')  # Remove trailing comma before array end
                
                questions_data = json.loads(fixed_text)
                logging.info(f" Fixed JSON parsing for {username}")
            except json.JSONDecodeError:
                # If still can't parse, raise the original error
                raise json_error
        
        #  Validate questions structure
        if not isinstance(questions_data, list) or len(questions_data) != 5:
            raise ValueError(f"Invalid questions format: expected list of 5 items, got {type(questions_data)} with {len(questions_data) if isinstance(questions_data, list) else 'unknown'} items")
        
        #  Validate each question structure
        for i, q in enumerate(questions_data):
            if not isinstance(q, dict) or 'id' not in q or 'type' not in q or 'question' not in q:
                raise ValueError(f"Invalid question structure at index {i}")
            
            if q['type'] == 'mcq' and 'options' not in q:
                raise ValueError(f"MCQ question at index {i} missing options")
        
        logging.info(f" User {username} (ID: {user_id}) - Successfully generated {len(questions_data)} personalized questions")
        
        return jsonify({
            "questions": questions_data, 
            "user_context": {
                "username": username,
                "user_id": user_id,
                "emotion": emotion,
                "chat_messages": len(history),
                "key_themes": key_themes,
                "personalization_level": "high" if len(history) > 10 else "moderate"
            }
        })
        
    except (json.JSONDecodeError, ValueError, Exception) as e:
        logging.error(f" Error generating personalized questions for {username}: {e}. Serving contextual fallback.")
        
        #  ENHANCED: More reliable fallback questions based on emotion
        if emotion in ['Sadness', 'Grief', 'Loneliness']:
            fallback_questions = [
                {"id": "f1", "type": "open", "question": f"Hi {username}, what's been weighing most heavily on your mind lately?"},
                {"id": "f2", "type": "mcq", "question": f"How would you describe your energy levels recently, {username}?", "options": ["Very low", "Low", "Moderate", "Good"]},
                {"id": "f3", "type": "open", "question": f"What activities used to bring you joy that feel different now, {username}?"},
                {"id": "f4", "type": "open", "question": f"Is there someone you feel comfortable talking to about your feelings, {username}?"},
                {"id": "f5", "type": "mcq", "question": f"How has your sleep been affected, {username}?", "options": ["Very poor", "Poor", "Fair", "Good"]}
            ]
        elif emotion in ['Anxiety', 'Stress', 'Fear']:
            fallback_questions = [
                {"id": "f1", "type": "open", "question": f"What situation tends to trigger your anxiety the most, {username}?"},
                {"id": "f2", "type": "mcq", "question": f"How often do you experience anxious feelings, {username}?", "options": ["Daily", "Few times a week", "Weekly", "Rarely"]},
                {"id": "f3", "type": "open", "question": f"What coping strategies have you tried for managing stress, {username}?"},
                {"id": "f4", "type": "open", "question": f"What physical sensations do you notice when you're anxious, {username}?"},
                {"id": "f5", "type": "mcq", "question": f"How manageable does your stress feel right now, {username}?", "options": ["Overwhelming", "Very difficult", "Challenging", "Manageable"]}
            ]
        elif emotion in ['Joy', 'Hope']:
            fallback_questions = [
                {"id": "f1", "type": "open", "question": f"What's been the biggest source of happiness for you lately, {username}?"},
                {"id": "f2", "type": "mcq", "question": f"How optimistic are you feeling about the future, {username}?", "options": ["Very optimistic", "Quite positive", "Moderately hopeful", "Cautiously optimistic"]},
                {"id": "f3", "type": "open", "question": f"What goals are you most excited about pursuing, {username}?"},
                {"id": "f4", "type": "open", "question": f"Are there any challenges you're still working through, {username}?"},
                {"id": "f5", "type": "mcq", "question": f"How satisfied do you feel with your current situation, {username}?", "options": ["Very satisfied", "Quite satisfied", "Moderately satisfied", "Working towards satisfaction"]}
            ]
        else:
            fallback_questions = [
                {"id": "f1", "type": "open", "question": f"How would you describe your overall emotional state these days, {username}?"},
                {"id": "f2", "type": "mcq", "question": f"What's your general mood been like recently, {username}?", "options": ["Low", "Mixed", "Stable", "Positive"]},
                {"id": "f3", "type": "open", "question": f"What's one thing you'd like to change about your current situation, {username}?"},
                {"id": "f4", "type": "open", "question": f"What would 'feeling better' look like for you, {username}?"},
                {"id": "f5", "type": "mcq", "question": f"How well are you taking care of yourself lately, {username}?", "options": ["Struggling", "Basic care only", "Doing okay", "Taking good care"]}
            ]
        
        return jsonify({
            "questions": fallback_questions, 
            "user_context": {
                "username": username,
                "user_id": user_id,
                "emotion": emotion,
                "chat_messages": len(history),
                "key_themes": key_themes,
                "personalization_level": "fallback_reliable"
            }
        })


#  IMPROVED: Enhanced submit_test with better JSON handling
@app.route('/submit_test', methods=['POST'])
@login_required
def submit_test():
    """Submit test analysis with improved JSON handling"""
    user_id = g.current_user_id
    username = g.current_username
    
    try:
        data = request.get_json()
        answers = data.get('answers', {})
        user_context = data.get('user_context', {})
        
        logging.info(f" User {username} (ID: {user_id}) - Submitting test with {len(answers)} answers")
        
        formatted_answers = "\n".join([f"Q: {q}\nA: {a}" for q, a in answers.items()])
        
        #  Get user context but keep it concise
        emotion = get_user_emotion(user_id)
        chat_history = get_user_chat_history(user_id)
        key_themes = user_context.get('key_themes', 'general concerns')[:50]  # Limit length
        
        #  IMPROVED: Shorter prompt to avoid JSON truncation issues
        prompt = f"""
        Analyze {username}'s mental health test answers and provide analysis as JSON.

        User: {username}
        Emotion: {emotion}
        Themes: {key_themes}
        Chat history: {len(chat_history)} messages

        Test Answers:
        {formatted_answers[:1000]}

        Return JSON with these exact keys:
        {{
          "overall_assessment": "Brief assessment for {username}",
          "risk_level": "Low/Moderate/High",
          "key_insights": ["Insight 1", "Insight 2"],
          "strengths": ["Strength 1", "Strength 2"],
          "areas_for_attention": ["Area 1", "Area 2"],
          "recommendations": ["Rec 1", "Rec 2"],
          "encouraging_message": "Personal message for {username}",
          "professional_help_needed": false
        }}

        Keep each field concise and meaningful.
        """
        
        #  More conservative JSON config
        json_config = {
            "temperature": 0.1,
            "top_p": 0.7,
            "top_k": 20,
            "max_output_tokens": 1200,  # Reduced for stability
            "response_mime_type": "application/json",
        }
        
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt, generation_config=json_config)
        
        response_text = safe_extract_response_text(response)
        
        if not response_text:
            raise ValueError("No response from Gemini API")
        
        #  Clean and validate JSON
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        try:
            analysis_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSON error in test analysis for {username}: {e}")
            # Use fallback analysis
            analysis_data = {
                "overall_assessment": f"Based on your responses, {username}, you're navigating some challenges but showing resilience.",
                "risk_level": "Moderate",
                "key_insights": [f"You're experiencing {emotion} which is affecting your daily life", "You have good self-awareness about your situation"],
                "strengths": ["Self-awareness", "Willingness to seek support", "Openness to help"],
                "areas_for_attention": ["Emotional regulation", "Stress management", "Self-care practices"],
                "recommendations": [f"Consider speaking with a counselor, {username}", "Practice daily stress-reduction techniques", "Maintain social connections"],
                "encouraging_message": f"Remember {username}, seeking help shows strength, not weakness. You're taking positive steps forward.",
                "professional_help_needed": emotion in ['Sadness', 'Anxiety', 'Suicidal Desire', 'Grief']
            }
        
        #  Save test result
        test_result = {
            "answers": answers,
            "analysis": analysis_data,
            "user_emotion_at_test": emotion,
            "chat_history_length": len(chat_history),
            "key_themes": key_themes
        }
        save_user_test_result(user_id, test_result)
        
        logging.info(f" User {username} (ID: {user_id}) - Test analysis completed successfully")
        
        return jsonify({
            "success": True, 
            "analysis": analysis_data, 
            "user_id": user_id, 
            "username": username
        })
        
    except Exception as e:
        logging.error(f" Error analyzing test for {username} (ID: {user_id}): {e}")
        return jsonify({
            "success": False, 
            "error": f"Failed to analyze responses for {username}. Please try again."
        }), 500

# -----------------------
# Health Check & Admin Routes
# -----------------------
@app.route('/health')
def health_check():
    """System health check"""
    users_count = len(load_users())
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "users_count": users_count,
        "server": "Mindmate AI - Multi-User Support with Conversation Memory",
        "user_data_files": len([f for f in os.listdir(USER_DATA_DIR) if f.startswith('user_') and f.endswith('.json')]),
        "features": ["user_isolation", "conversation_memory", "personalized_tests", "contextual_responses"]
    })

@app.route('/admin/users')
def admin_users():
    """Admin endpoint to view users (debug only)"""
    if app.debug:
        users = load_users()
        user_files = {}
        
        for user_id in users:
            file_path = get_user_data_file(user_id)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        user_data = json.load(f)
                        user_files[user_id] = {
                            "username": user_data.get('username', f'User_{user_id}'),
                            "emotion": user_data.get('current_emotion', 'Unknown'),
                            "chat_messages": len(user_data.get('chat_history', [])),
                            "conversations": len(user_data.get('chat_history', [])) // 2,
                            "test_results": len(user_data.get('test_results', [])),
                            "last_updated": user_data.get('last_updated', 'Never')
                        }
                except:
                    user_files[user_id] = {"error": "Could not read user data"}
        
        return jsonify({
            "total_users": len(users),
            "users": {k: {**v, "password": "[HIDDEN]"} for k, v in users.items()},
            "user_data_summary": user_files
        })
    return "Access Denied", 403

# -----------------------
# Error Handlers
# -----------------------
@app.errorhandler(404)
def not_found_error(error):
    logging.warning(f"404 error: {request.url}")
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(error):
    logging.error(f"Internal server error: {error}")
    session.clear()
    return redirect(url_for('login'))

@app.errorhandler(403)
def forbidden_error(error):
    logging.warning(f"403 error: {request.url}")
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    print(f" Users file: {USERS_FILE}")
    print(f" User data directory: {USER_DATA_DIR}")
    print(f" Session timeout: 30 minutes")
    print(f" Multi-user isolation: ENABLED")
    print(f" Conversation memory: LAST 10 CHATS (20 messages)")
    print(f" Personalized tests with context: ENABLED")
    print(f" Contextual responses: ENABLED")
    print(" Server running at: http://127.0.0.1:5000")
    print("=" * 70)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
