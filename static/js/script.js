document.addEventListener('DOMContentLoaded', () => {
  // Navbar active
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) link.classList.add('active');
  });

  // Theme toggle
  const toggle = document.getElementById('theme-toggle');
  if (toggle) {
    const currentTheme = localStorage.getItem('theme') || 'bright';
    document.body.classList.add(currentTheme);
    toggle.textContent = currentTheme === 'bright' ? '🌧️' : '☀️';
    toggle.addEventListener('click', () => {
      const newTheme = document.body.classList.contains('bright') ? 'stormy' : 'bright';
      document.body.classList.remove('bright', 'stormy');
      document.body.classList.add(newTheme);
      localStorage.setItem('theme', newTheme);
      toggle.textContent = newTheme === 'bright' ? '🌧️' : '☀️';
      const url = new URL(window.location);
      url.searchParams.set('theme', newTheme);
      window.history.replaceState({}, '', url);
    });
  }

  // Lang switch (form submit handles, but add smooth)
  const langForm = document.querySelector('form[action="/set_language"]');
  if (langForm) {
    langForm.addEventListener('submit', (e) => {
      // Optional: Add loading
      document.body.style.opacity = '0.7';
    });
  }

  // CSV export
  window.exportToCSV = (predictions) => {
    let csv = 'Type,Inputs,Output,Timestamp\n';
    predictions.forEach(p => csv += `${p.type},"${p.inputs.replace(/"/g, '""')}",${p.output},${p.timestamp}\n`);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'predictions.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  // Smooth scroll
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelector(anchor.getAttribute('href')).scrollIntoView({ behavior: 'smooth' });
    });
  });
});

// Chat updates
function loadChatMessages(chatId) {
  fetch(`/shop/chat/messages/${chatId}`)
    .then(response => response.json())
    .then(messages => {
      const container = document.getElementById('chat-messages');
      container.innerHTML = '';
      messages.forEach(msg => {
        const li = document.createElement('li');
        li.className = `message ${msg.sender === '{{ current_user.username }}' ? 'sent' : 'received'}`;
        li.innerHTML = `<strong>${msg.sender}:</strong> ${msg.content} <small>${new Date(msg.timestamp).toLocaleString()}</small>`;
        container.appendChild(li);
      });
      container.scrollTop = container.scrollHeight;
    });
}

// Auto-refresh chat every 5s
setInterval(() => loadChatMessages(chatId), 5000);  // Define chatId from URL