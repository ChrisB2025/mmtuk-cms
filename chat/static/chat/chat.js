/* MMTUK CMS — Chat JavaScript */

(function () {
  const messagesEl = document.getElementById('messages');
  const chatForm = document.getElementById('chatForm');
  const messageInput = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const typingIndicator = document.getElementById('typingIndicator');
  const uploadBtn = document.getElementById('uploadBtn');
  const pdfFileInput = document.getElementById('pdfFileInput');

  if (!chatForm || !messageInput) return;

  // Auto-resize textarea
  messageInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
  });

  // Enter to send (Shift+Enter for newline)
  messageInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(messageInput.value);
    }
  });

  // Scroll to bottom
  function scrollToBottom() {
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  // Append a message to the chat
  function appendMessage(role, content) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message message-' + role;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';

    if (role === 'assistant') {
      contentEl.classList.add('markdown-body');
      try {
        contentEl.innerHTML = marked.parse(content);
      } catch (e) {
        contentEl.textContent = content;
      }
    } else {
      contentEl.textContent = content;
    }

    bubble.appendChild(contentEl);
    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    scrollToBottom();
  }

  // Show/hide typing indicator
  function setTyping(show) {
    if (typingIndicator) {
      typingIndicator.style.display = show ? 'block' : 'none';
    }
    if (show) scrollToBottom();
  }

  // Show action result as a toast notification
  function showActionAlert(message, type) {
    if (window.showToast) window.showToast(message, type === 'error' ? 'error' : 'success');
  }

  // Send message
  async function sendMessage(text) {
    if (!text.trim()) return;

    if (!window.SEND_URL) {
      appendMessage('assistant', 'Chat session expired. Please refresh the page.');
      return;
    }

    // Disable input while sending
    messageInput.disabled = true;
    sendBtn.disabled = true;
    sendBtn.classList.add('btn-loading');

    // Remove empty-chat placeholder if present
    const emptyChat = messagesEl.querySelector('.empty-chat');
    if (emptyChat) emptyChat.remove();

    appendMessage('user', text);
    messageInput.value = '';
    messageInput.style.height = 'auto';
    setTyping(true);

    // If message is just a bare URL, add context so Cloudflare WAF doesn't block it
    var sendText = text.trim();
    if (/^https?:\/\/\S+$/i.test(sendText)) {
      sendText = 'I want to add this article: ' + sendText;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 min (match gunicorn)

    try {
      const resp = await fetch(window.SEND_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.CSRF_TOKEN,
        },
        body: JSON.stringify({ message: sendText }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      setTyping(false);

      if (resp.status === 429) {
        appendMessage('assistant', 'You\'ve sent too many messages. Please wait a moment before trying again.');
        return;
      }

      if (!resp.ok) {
        appendMessage('assistant', 'Sorry, something went wrong. Please try again.');
        return;
      }

      const ct = resp.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        appendMessage('assistant', 'Unexpected server response. Please try refreshing the page.');
        return;
      }

      const data = await resp.json();
      if (data.response && data.response.trim()) {
        appendMessage('assistant', data.response);
      }

      if (data.action_taken) {
        const action = data.action_taken;
        if (action.type === 'content_created') {
          showActionAlert('Content published: ' + action.title, 'success');
        } else if (action.type === 'content_edited') {
          showActionAlert('Content updated: ' + action.title, 'success');
        } else if (action.type === 'content_deleted') {
          showActionAlert('Content deleted: ' + action.title, 'success');
        } else if (action.type === 'draft_pending') {
          showActionAlert('Draft saved for approval', 'success');
        } else if (action.type === 'error') {
          showActionAlert(action.message, 'error');
        }
      }

    } catch (err) {
      clearTimeout(timeoutId);
      setTyping(false);
      console.error('chat send failed:', err.name, err.message, 'SEND_URL:', window.SEND_URL);
      if (err.name === 'AbortError') {
        appendMessage('assistant', 'This is taking longer than expected. The content may still be processing \u2014 try refreshing the page in a minute to check.');
      } else {
        appendMessage('assistant', 'Network error. Please check your connection and try again.');
      }
    } finally {
      messageInput.disabled = false;
      sendBtn.disabled = false;
      sendBtn.classList.remove('btn-loading');
      messageInput.focus();
    }
  }

  chatForm.addEventListener('submit', function (e) {
    e.preventDefault();
    sendMessage(messageInput.value);
  });

  // --- PDF Upload ---

  async function uploadPdf(file) {
    if (!file) return;

    messageInput.disabled = true;
    sendBtn.disabled = true;
    sendBtn.classList.add('btn-loading');

    // Remove empty-chat/suggested-actions placeholder if present
    const emptyChat = messagesEl.querySelector('.empty-chat');
    if (emptyChat) emptyChat.remove();

    var docType = file.name.toLowerCase().endsWith('.docx') ? 'Word document' : 'PDF';
    appendMessage('user', '[Uploading ' + docType + ': ' + file.name + ']');
    setTyping(true);

    var formData = new FormData();
    formData.append('pdf', file);

    try {
      const resp = await fetch(window.UPLOAD_PDF_URL, {
        method: 'POST',
        headers: {
          'X-CSRFToken': window.CSRF_TOKEN,
        },
        body: formData,
      });

      setTyping(false);

      if (resp.status === 429) {
        appendMessage('assistant', 'You\'ve sent too many messages. Please wait a moment before trying again.');
        return;
      }

      if (!resp.ok) {
        var errData = {};
        try { errData = await resp.json(); } catch (e) {}
        appendMessage('assistant', errData.error || 'Sorry, something went wrong uploading the PDF.');
        return;
      }

      const data = await resp.json();
      if (data.response && data.response.trim()) {
        appendMessage('assistant', data.response);
      }

      if (data.action_taken) {
        const action = data.action_taken;
        if (action.type === 'content_created') {
          showActionAlert('Content published: ' + action.title, 'success');
        } else if (action.type === 'draft_pending') {
          showActionAlert('Draft saved for approval', 'success');
        } else if (action.type === 'error') {
          showActionAlert(action.message, 'error');
        }
      }

    } catch (err) {
      setTyping(false);
      appendMessage('assistant', 'Network error. Please check your connection and try again.');
    } finally {
      messageInput.disabled = false;
      sendBtn.disabled = false;
      sendBtn.classList.remove('btn-loading');
      messageInput.focus();
    }
  }

  if (uploadBtn) {
    uploadBtn.addEventListener('click', function () {
      if (pdfFileInput) pdfFileInput.click();
    });
  }

  if (pdfFileInput) {
    pdfFileInput.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        uploadPdf(this.files[0]);
        this.value = '';  // Reset so same file can be re-selected
      }
    });
  }

  // --- Suggested Action Buttons ---

  document.querySelectorAll('.btn-action').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var actionType = this.getAttribute('data-action-type');
      var message = this.getAttribute('data-message');

      if (actionType === 'upload') {
        if (pdfFileInput) pdfFileInput.click();
      } else if (actionType === 'send' && message) {
        messageInput.value = message;
        sendMessage(message);
      }
    });
  });

  // Initial scroll to bottom
  scrollToBottom();
})();
