/* MMTUK CMS — Chat JavaScript */

(function () {
  const messagesEl = document.getElementById('messages');
  const chatForm = document.getElementById('chatForm');
  const messageInput = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const typingIndicator = document.getElementById('typingIndicator');
  const actionAlert = document.getElementById('actionAlert');
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
      chatForm.dispatchEvent(new Event('submit'));
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
      contentEl.innerHTML = marked.parse(content);
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

  // Show action result alert
  function showActionAlert(message, type) {
    if (!actionAlert) return;
    actionAlert.textContent = message;
    actionAlert.style.display = 'block';
    actionAlert.style.background = type === 'error' ? '#ef4444' : '#10b981';
    setTimeout(function () {
      actionAlert.style.display = 'none';
    }, 5000);
  }

  // Send message
  async function sendMessage(text) {
    if (!text.trim()) return;

    // Disable input while sending
    messageInput.disabled = true;
    sendBtn.disabled = true;

    // Remove empty-chat placeholder if present
    const emptyChat = messagesEl.querySelector('.empty-chat');
    if (emptyChat) emptyChat.remove();

    appendMessage('user', text);
    messageInput.value = '';
    messageInput.style.height = 'auto';
    setTyping(true);

    try {
      const resp = await fetch(window.SEND_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.CSRF_TOKEN,
        },
        body: JSON.stringify({ message: text }),
      });

      setTyping(false);

      if (resp.status === 429) {
        appendMessage('assistant', 'You\'ve sent too many messages. Please wait a moment before trying again.');
        return;
      }

      if (!resp.ok) {
        appendMessage('assistant', 'Sorry, something went wrong. Please try again.');
        return;
      }

      const data = await resp.json();
      appendMessage('assistant', data.response);

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
      setTyping(false);
      appendMessage('assistant', 'Network error. Please check your connection and try again.');
    } finally {
      messageInput.disabled = false;
      sendBtn.disabled = false;
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

    // Remove empty-chat/suggested-actions placeholder if present
    const emptyChat = messagesEl.querySelector('.empty-chat');
    if (emptyChat) emptyChat.remove();

    appendMessage('user', '[Uploading PDF: ' + file.name + ']');
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
      appendMessage('assistant', data.response);

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
