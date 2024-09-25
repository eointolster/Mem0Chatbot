from flask import Flask, render_template, request, jsonify, session, redirect
from flask_session import Session
from mem0 import Memory
from config import config
import requests
import json
import logging

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a strong secret key
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Memory with the configuration
m = Memory.from_config(config)

# Dictionary to store conversation history per user
user_conversations = {}

# Ollama LLM Configuration
llm_config = config['llm']['config']
ollama_base_url = llm_config.get('ollama_base_url', 'http://localhost:11434')
llm_model = llm_config.get('model', 'llama3.1:latest')

def normalize_text(text):
    """Normalize text by converting to lowercase and stripping whitespace."""
    return text.lower().strip()

def generate_response(prompt):
    payload = {
        "model": llm_model,
        "prompt": prompt,
        "temperature": llm_config.get('temperature', 0.7),
        "max_tokens": llm_config.get('max_tokens', 150)
    }

    try:
        response = requests.post(f"{ollama_base_url}/api/generate", json=payload, stream=True, timeout=30)

        if response.status_code == 200:
            bot_response = ''
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    data = json.loads(decoded_line)
                    bot_response += data.get('response', '')
            return bot_response.strip()
        else:
            logger.error(f"Ollama API Error: {response.status_code} {response.text}")
            return "I'm sorry, I couldn't generate a response."
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return "I'm sorry, I couldn't generate a response."

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html')
    else:
        return render_template('index.html')  # This will show the login form

@app.route('/login', methods=['POST'])
def login():
    username = request.json['username']
    session['username'] = username
    return jsonify({'success': True})

@app.route('/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_message = request.json['message']
    user_id = session['username']

    # Initialize conversation history if not present
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    # Append user message
    user_conversations[user_id].append({'sender': 'user', 'message': user_message})

    # Keep only the last 10 messages (20 entries including user and bot)
    if len(user_conversations[user_id]) > 20:
        user_conversations[user_id] = user_conversations[user_id][-20:]

    # Check for '/delete_memories' command
    if user_message.strip().lower() == '/delete_memories':
        try:
            m.delete_all(user_id=user_id)
            bot_response = "All memories have been deleted successfully."
            logger.info(f"Memories deleted for user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting memories for user {user_id}: {e}")
            bot_response = "An error occurred while trying to delete memories. Please try again later."
    
    # Check for '/Store' command
    elif user_message.startswith('/Store'):
        memory_content = user_message[len('/Store'):].strip()
        try:
            result = m.add(memory_content, user_id=user_id)
            logger.info(f"Memory storage result for user {user_id}: {result}")
            bot_response = "Memory stored successfully."
        except Exception as e:
            logger.error(f"Error storing memory for user {user_id}: {str(e)}")
            bot_response = f"Failed to store memory. Error: {str(e)}"
        
        logger.info(f"Bot response for memory storage: {bot_response}")
    
    else:
        # Prepare conversation history for context
        conversation_history = '\n'.join(
            [f"{'User' if msg['sender'] == 'user' else 'Assistant'}: {msg['message']}" 
             for msg in user_conversations[user_id]]
        )

        try:
            # Retrieve all memories for the user
            all_memories = m.get_all(user_id=user_id)
            memory_context = "Here are all the memories I have about you:\n" + '\n'.join(
                [f"- {mem['memory']}" for mem in all_memories]
            ) if all_memories else "I don't have any specific memories about you yet."

            # Normalize user message for searching
            normalized_message = normalize_text(user_message)

            # Check for specific questions about user information
            if any(keyword in normalized_message for keyword in ['my name', 'who am i', 'what is my']):
                relevant_memories = [mem for mem in all_memories if any(keyword in mem['memory'].lower() for keyword in ['name', 'user', 'id'])]
            else:
                # Perform similarity search
                similar_memories = m.search(normalized_message, limit=5, user_id=user_id)
                logger.info(f"Similar memories found for user {user_id}: {similar_memories}")
                relevant_memories = [memory for memory in similar_memories if memory.get('score', 0) > 0.5]

            if relevant_memories:
                relevant_context = "Relevant memories:\n" + "\n".join([mem['memory'] for mem in relevant_memories])
            else:
                relevant_context = "I don't have any specific memories relevant to this query."

            prompt = f"""You are a helpful assistant with access to the user's memories. 
            Here's all the memory context: {memory_context}
            
            Here's the relevant memory context: {relevant_context}

            Here's the entire conversation history:
            {conversation_history}

            User: {user_message}
            Assistant: Respond to the user's latest message using the provided memories and conversation history. Be concise and direct in your response. If asked about specific user information (like name), use the relevant memories to answer accurately."""

            bot_response = generate_response(prompt)

        except Exception as e:
            logger.error(f"Error in chat processing: {e}")
            bot_response = "I'm sorry, I encountered an error while processing your request. Please try again."

    # Append bot response
    user_conversations[user_id].append({'sender': 'bot', 'message': bot_response})

    return jsonify({'response': bot_response})

@app.route('/get_conversation', methods=['GET'])
def get_conversation():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['username']
    conversation = user_conversations.get(user_id, [])
    return jsonify({'conversation': conversation})

@app.route('/list_memories', methods=['GET'])
def list_memories():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['username']
    try:
        memories = m.get_all(user_id=user_id)
        return jsonify({'memories': memories})
    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        return jsonify({'error': 'Failed to retrieve memories'}), 500

@app.route('/delete_memories', methods=['POST'])
def delete_memories():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['username']
    try:
        m.delete_all(user_id=user_id)
        return jsonify({'status': 'All memories deleted'})
    except Exception as e:
        logger.error(f"Error deleting memories: {e}")
        return jsonify({'error': 'Failed to delete memories'}), 500

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)