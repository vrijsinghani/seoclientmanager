class ChatManager {
    constructor() {
        this.socket = null;
        this.selectedAgentId = null;
        this.isProcessing = false;
        this.isReconnecting = false;
        
        // Initialize everything after DOM is loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
    }

    initialize() {
        if (!this.initializeElements()) {
            console.error('Failed to initialize elements');
            return;
        }
        this.initializeWebSocket();
        this.bindEvents();
    }

    initializeElements() {
        this.elements = {
            agentSelect: document.getElementById('agent-select'),
            modelSelect: document.getElementById('model-select'),
            clientSelect: document.getElementById('client-select'),
            messageInput: document.getElementById('message-input'),
            sendButton: document.getElementById('send-message'),
            newChatBtn: document.getElementById('new-chat-btn'),
            chatMessages: document.getElementById('chat-messages'),
            connectionStatus: document.getElementById('connection-status'),
            agentAvatar: document.querySelector('#agent-avatar img'),
            agentName: document.getElementById('agent-name')
        };

        // Check if all required elements are present
        const requiredElements = [
            'agentSelect', 'modelSelect', 'clientSelect', 
            'messageInput', 'sendButton', 'chatMessages'
        ];

        const missingElements = requiredElements.filter(
            elementName => !this.elements[elementName]
        );

        if (missingElements.length > 0) {
            console.error('Missing required elements:', missingElements);
            return false;
        }

        // Set initial agent selection
        if (this.elements.agentSelect.options.length > 0) {
            const firstOption = this.elements.agentSelect.options[0];
            this.selectedAgentId = firstOption.value;
            
            // Update agent info if elements exist
            if (this.elements.agentAvatar && firstOption.dataset.avatar) {
                this.elements.agentAvatar.src = firstOption.dataset.avatar;
            }
            if (this.elements.agentName && firstOption.dataset.name) {
                this.elements.agentName.textContent = firstOption.dataset.name;
            }
        }

        // Safely initialize autosize
        this.initializeAutosize();
        return true;
    }

    initializeAutosize() {
        if (typeof autosize === 'function') {
            autosize(this.elements.messageInput);
        } else {
            console.warn('Autosize plugin not loaded. Textarea will not auto-resize.');
            // Set a default height for the textarea
            this.elements.messageInput.style.minHeight = '50px';
            this.elements.messageInput.style.maxHeight = '200px';
        }
    }

    bindEvents() {
        // Agent selection
        this.elements.agentSelect.addEventListener('change', () => this.handleAgentSelection());

        // Message sending
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // New chat
        this.elements.newChatBtn.addEventListener('click', () => this.startNewChat());

        // Connection management
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        window.addEventListener('beforeunload', () => this.closeWebSocket());

        // Add event listener for Ctrl+Enter
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault(); // Prevent default newline
                this.sendMessage();
            }
        });
    }

    initializeWebSocket() {
        const wsScheme = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const wsPath = `${wsScheme}${window.location.host}/ws/chat/`;
        
        console.log('Initializing WebSocket connection to:', wsPath);
        this.socket = new WebSocket(wsPath);
        
        this.socket.onopen = () => {
            console.log('WebSocket connection opened');
            this.handleSocketOpen();
        };
        
        this.socket.onmessage = (event) => {
            console.log('WebSocket message received:', event.data);
            try {
                const data = JSON.parse(event.data);
                console.log('Parsed WebSocket data:', data);
                this.processMessageData(data);
            } catch (error) {
                console.error('Error processing message:', error);
                this.handleError('Failed to process message');
            }
        };
        
        this.socket.onclose = (event) => {
            console.log('WebSocket connection closed:', event);
            this.handleSocketClose(event);
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.handleSocketError(error);
        };
    }

    appendMessage(message, isAgent = false) {
        if (!this.elements.chatMessages) return;

        console.log('Appending message:', {
            message: message.substring(0, 100) + '...',
            isAgent: isAgent,
            hasHTML: message.includes('<table') || message.includes('<div')
        });

        const messageDiv = document.createElement('div');
        messageDiv.className = isAgent ? 'agent-message' : 'user-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (isAgent) {
            // For agent messages, handle HTML and markdown
            if (message.includes('<table') || message.includes('<div')) {
                // Direct HTML content
                console.log('Rendering HTML content');
                contentDiv.innerHTML = message;

                // Add Bootstrap classes to table if not already present
                const table = contentDiv.querySelector('table');
                if (table) {
                    table.classList.add('table', 'table-striped', 'table-hover', 'table-sm');
                    
                    // Add Bootstrap classes to thead and tbody
                    const thead = table.querySelector('thead');
                    if (thead) {
                        thead.classList.add('table-dark');
                    }
                }
            } else if (message.startsWith('{') || message.startsWith('[')) {
                // Try to parse and format JSON
                try {
                    const parsed = JSON.parse(message);
                    contentDiv.innerHTML = `<pre class="json-output">${JSON.stringify(parsed, null, 2)}</pre>`;
                } catch (e) {
                    // If JSON parsing fails, treat as markdown
                    contentDiv.innerHTML = marked.parse(message);
                }
            } else {
                // Regular markdown content
                contentDiv.innerHTML = marked.parse(message);
            }
            
            // Add agent info
            if (this.elements.agentAvatar && this.elements.agentName) {
                const agentInfo = document.createElement('div');
                agentInfo.className = 'd-flex align-items-center mb-2';
                
                const avatar = document.createElement('img');
                avatar.src = this.elements.agentAvatar.src;
                avatar.className = 'avatar-img rounded-circle me-2';
                avatar.style.width = '24px';
                avatar.style.height = '24px';
                
                const name = document.createElement('span');
                name.className = 'text-dark font-weight-bold text-sm';
                name.textContent = this.elements.agentName.textContent;
                
                agentInfo.appendChild(avatar);
                agentInfo.appendChild(name);
                contentDiv.insertBefore(agentInfo, contentDiv.firstChild);
            }
        } else {
            // User messages are always plain text
            contentDiv.textContent = message;
        }
        
        messageDiv.appendChild(contentDiv);
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'chat-message agent typing-indicator';
        indicator.innerHTML = `
            <div class="message-content">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        this.elements.chatMessages.appendChild(indicator);
        this.scrollToBottom();
        return indicator;
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    handleAgentSelection() {
        const selectedOption = this.elements.agentSelect.selectedOptions[0];
        if (!selectedOption) return;

        this.selectedAgentId = this.elements.agentSelect.value;

        // Safely update agent avatar
        if (this.elements.agentAvatar && selectedOption.dataset.avatar) {
            this.elements.agentAvatar.src = selectedOption.dataset.avatar;
        }
        
        // Safely update agent name
        if (this.elements.agentName && selectedOption.dataset.name) {
            this.elements.agentName.textContent = selectedOption.dataset.name;
        }
    }

    processMessageData(data) {
        // Log received data
        console.log('Processing message data:', {
            type: data.type,
            message: data.message,
            error: data.error,
            timestamp: data.timestamp
        });
        
        if (data.error) {
            console.error('Error in message data:', data.message);
            this.handleError(data.message);
            return;
        }

        if (data.type === 'keep_alive_response') {
            console.log('Received keep-alive response');
            return;
        }

        // Remove typing indicator if exists
        if (this._currentTypingIndicator) {
            console.log('Removing typing indicator');
            this._currentTypingIndicator.remove();
            this._currentTypingIndicator = null;
        }

        // Process message based on type
        if (data.type === 'user_message') {
            console.log('Appending user message:', data.message);
            this.appendMessage(data.message, false);
        } else if (data.type === 'agent_message') {
            console.log('Appending agent message:', data.message);
            let message = data.message;
            
            // Try to parse if it's a JSON string
            try {
                const parsed = JSON.parse(message);
                if (parsed.actions || parsed.steps) {
                    // This is an intermediate message, create collapsible view
                    console.log('Creating collapsible for intermediate message');
                    this.appendIntermediateMessage(parsed);
                    return;
                }
            } catch (e) {
                // Not JSON, continue with message as is
            }

            // Handle regular messages
            if (message.includes('<table') || message.includes('<div')) {
                console.log('Using HTML content directly');
                this.appendMessage(message, true);
            } else {
                // Try to detect markdown table format
                if (message.includes('|') && message.includes('\n')) {
                    console.log('Converting markdown table to HTML');
                    const lines = message.trim().split('\n');
                    let html = '<table class="table table-striped table-hover table-sm"><thead><tr>';
                    
                    // Process headers
                    const headers = lines[0].split('|').map(h => h.trim()).filter(h => h);
                    headers.forEach(header => {
                        html += `<th>${header}</th>`;
                    });
                    html += '</tr></thead><tbody>';
                    
                    // Skip header and separator lines
                    for (let i = 2; i < lines.length; i++) {
                        const cells = lines[i].split('|').map(c => c.trim()).filter(c => c);
                        if (cells.length) {
                            html += '<tr>';
                            cells.forEach(cell => {
                                html += `<td>${cell}</td>`;
                            });
                            html += '</tr>';
                        }
                    }
                    html += '</tbody></table>';
                    this.appendMessage(html, true);
                } else {
                    this.appendMessage(message, true);
                }
            }
        }

        this.isProcessing = false;
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = false;
        }
    }

    appendIntermediateMessage(data) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'agent-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content intermediate-message';
        
        // Create collapsible structure
        const header = document.createElement('div');
        header.className = 'intermediate-header d-flex align-items-center';
        
        // Add appropriate icon and title based on content
        if (data.actions) {
            header.innerHTML = `
                <i class="fas fa-cog me-2"></i>
                <span>Action: ${data.actions[0].tool}</span>
            `;
        } else if (data.steps) {
            header.innerHTML = `
                <i class="fas fa-list-check me-2"></i>
                <span>Processing Step</span>
            `;
        }
        
        // Add expand/collapse button
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-link btn-sm ms-auto';
        toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
        header.appendChild(toggleBtn);
        
        // Create collapsible content
        const collapseDiv = document.createElement('div');
        collapseDiv.className = 'intermediate-content collapse';
        collapseDiv.innerHTML = `<pre class="json-output">${JSON.stringify(data, null, 2)}</pre>`;
        
        // Add event listener for toggle
        toggleBtn.addEventListener('click', () => {
            const isCollapsed = collapseDiv.classList.contains('show');
            if (isCollapsed) {
                collapseDiv.classList.remove('show');
                toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
            } else {
                collapseDiv.classList.add('show');
                toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
            }
        });
        
        contentDiv.appendChild(header);
        contentDiv.appendChild(collapseDiv);
        messageDiv.appendChild(contentDiv);
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    handleError(message) {
        console.error('Error:', message);
        
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = false;
        }
        
        // Show error message
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: 'Error',
                text: message,
                icon: 'error',
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 3000,
                timerProgressBar: true
            });
        }
        
        this.isProcessing = false;
    }

    startNewChat() {
        Swal.fire({
            title: 'Start New Chat?',
            text: 'This will clear the current conversation.',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Yes, start new',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                this.elements.chatMessages.innerHTML = '';
                this.elements.messageInput.value = '';
                
                // Safely update autosize
                if (typeof autosize === 'function') {
                    autosize.update(this.elements.messageInput);
                }
                
                Swal.fire({
                    icon: 'success',
                    title: 'New Chat Started',
                    toast: true,
                    position: 'bottom-end',
                    showConfirmButton: false,
                    timer: 3000,
                    timerProgressBar: true
                });
            }
        });
    }

    async reconnectWebSocket() {
        if (this.isReconnecting) return;
        
        this.isReconnecting = true;
        this.updateConnectionStatus('Reconnecting...', 'warning');
        
        try {
            await this.closeWebSocket();
            await new Promise(resolve => setTimeout(resolve, 1000));
            this.initializeWebSocket();
        } finally {
            this.isReconnecting = false;
        }
    }

    updateConnectionStatus(message, status = 'success') {
        const dot = this.elements.connectionStatus.querySelector('.connection-dot');
        
        // Remove all status classes
        dot.classList.remove('connected', 'connecting');
        
        // Add appropriate class based on status
        switch(status) {
            case 'success':
                dot.classList.add('connected');
                break;
            case 'warning':
                dot.classList.add('connecting');
                break;
            case 'error':
                // Default red state (no class needed)
                break;
        }
        
        this.elements.connectionStatus.setAttribute('title', message);
        
        // Initialize or update tooltip
        if (!this.elements.connectionStatus._tooltip) {
            this.elements.connectionStatus._tooltip = new bootstrap.Tooltip(this.elements.connectionStatus);
        } else {
            this.elements.connectionStatus._tooltip.dispose();
            this.elements.connectionStatus._tooltip = new bootstrap.Tooltip(this.elements.connectionStatus);
        }
    }

    handleSocketOpen() {
        this.updateConnectionStatus('Connected', 'success');
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = false;
        }
        this.setupKeepAlive();
    }

    handleSocketClose(event) {
        this.updateConnectionStatus('Disconnected', 'error');
        this.elements.sendButton.disabled = true;
        
        if (!this.isReconnecting) {
            setTimeout(() => this.reconnectWebSocket(), 5000);
        }
    }

    handleSocketError(error) {
        console.error('WebSocket error:', error);
        this.updateConnectionStatus('Connection Error', 'error');
    }

    handleVisibilityChange() {
        if (document.visibilityState === 'visible') {
            if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
                this.reconnectWebSocket();
            }
        }
    }

    setupKeepAlive() {
        this.keepAliveInterval = setInterval(() => {
            if (this.socket?.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({
                    type: 'keep_alive',
                    timestamp: Date.now()
                }));
            }
        }, 25000);
    }

    async closeWebSocket() {
        if (this.keepAliveInterval) {
            clearInterval(this.keepAliveInterval);
        }
        
        if (this.socket) {
            this.socket.onclose = null; // Prevent reconnection attempt
            this.socket.close();
            this.socket = null;
        }
    }

    sendMessage() {
        if (this.isProcessing) {
            console.log('Message processing in progress, ignoring send request');
            return;
        }

        const message = this.elements.messageInput.value.trim();
        if (!message) {
            console.log('Empty message, ignoring send request');
            return;
        }

        if (!this.selectedAgentId) {
            console.log('No agent selected');
            Swal.fire({
                title: 'Select an Agent',
                text: 'Please select an agent before sending messages.',
                icon: 'warning',
                confirmButtonText: 'OK'
            });
            return;
        }

        if (this.socket?.readyState !== WebSocket.OPEN) {
            console.log('WebSocket not connected, attempting reconnection');
            this.reconnectWebSocket();
            return;
        }

        this.isProcessing = true;
        this.elements.sendButton.disabled = true;
        
        const payload = {
            message,
            agent_id: this.selectedAgentId,
            model: this.elements.modelSelect.value,
            client_id: this.elements.clientSelect.value
        };

        console.log('Sending message payload:', payload);

        try {
            this.socket.send(JSON.stringify(payload));
            this.elements.messageInput.value = '';
            
            if (typeof autosize === 'function') {
                autosize.update(this.elements.messageInput);
            }
            
            const typingIndicator = this.showTypingIndicator();
            this._currentTypingIndicator = typingIndicator;
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.handleError('Failed to send message');
        }
    }
} 