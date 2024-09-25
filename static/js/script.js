function login() {
    const usernameInput = document.getElementById('username-input');
    const username = usernameInput.value.trim();

    if (username) {
        fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username: username }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('login-container').style.display = 'none';
                document.querySelector('.chat-container').style.display = 'flex';
                loadConversation();
            } else {
                alert('Login failed.');
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    }
}

function sendMessage() {
    const userInput = document.getElementById('user-input');
    const message = userInput.value.trim();

    if (message) {
        addMessageToChat('user', message);
        userInput.value = '';

        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else {
                addMessageToChat('bot', data.response);
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    }
}

function addMessageToChat(sender, message) {
    const chatMessages = document.getElementById('chat-messages');
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender + '-message');
    messageElement.textContent = message;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function loadConversation() {
    fetch('/get_conversation')
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            const chatMessages = document.getElementById('chat-messages');
            chatMessages.innerHTML = '';
            data.conversation.forEach(item => {
                addMessageToChat(item.sender, item.message);
            });
        }
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

document.getElementById('user-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

document.getElementById('username-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        login();
    }
});
