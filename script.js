const BACKEND_URL = "http://192.168.20.111:8000";

function getSessionId() {
  const sessionKey = "session_id";
  let sessionId = localStorage.getItem(sessionKey);

  if (!sessionId) {
    // Fallback UUID generator (v4 style)
    sessionId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
    localStorage.setItem(sessionKey, sessionId);
  }

  return sessionId;
}


const speechSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
let recognition;
if (speechSupported) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = 'id-ID';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  const micBtn = document.getElementById('micBtn');
  const input = document.getElementById('pesan');
  micBtn.style.display = 'inline-block';

  micBtn.addEventListener('click', () => {
    recognition.start();
    micBtn.classList.add('listening');
  });

  recognition.onresult = (event) => {
    input.value = event.results[0][0].transcript;
    micBtn.classList.remove('listening');
    input.focus();
  };

  recognition.onerror = (event) => {
    micBtn.classList.remove('listening');
    let errorMessage = "Terjadi error pada pengenalan suara.";
    switch (event.error) {
      case 'not-allowed':
        errorMessage = "Mohon izinkan akses mikrofon untuk menggunakan fitur suara.";
        break;
      case 'no-speech':
        errorMessage = "Tidak ada suara terdeteksi. Mohon coba lagi.";
        break;
    }
    tampilkanPesan(`⚠️ ${errorMessage}`, "bot");
  };

  recognition.onend = () => micBtn.classList.remove('listening');
} else {
  document.getElementById('micBtn').style.display = 'none';
}

document.getElementById("fileInput").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file && file.type !== 'text/plain') {
    alert("Hanya file .txt yang didukung.");
    event.target.value = "";
  }
});

const sendButton = document.querySelector('.input-area button:last-child');

async function kirim() {
  const input = document.getElementById('pesan');
  const fileInput = document.getElementById('fileInput');
  const pesan = input.value.trim();
  const file = fileInput.files[0];

  if (!pesan && !file) return;

  tampilkanPesan(pesan || '[File dikirim]', 'user');
  input.value = "";
  fileInput.value = "";

  let fileText = "";
  sendButton.disabled = true;

  if (file) {
    const reader = new FileReader();
    reader.onload = async () => {
      fileText = reader.result;
      tampilkanPesan(`<strong>📎 ${file.name}</strong>`, "user");
      await kirimKeBackend(pesan, fileText);
      sendButton.disabled = false;
    };
    reader.readAsText(file);
  } else {
    await kirimKeBackend(pesan, fileText);
    sendButton.disabled = false;
  }
}

async function kirimKeBackend(message, fileText) {
  const sessionId = getSessionId();
  tampilkanTyping();

  try {
    const res = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, file: fileText })
    });
    const data = await res.json();
    console.log("🔁 Reply dari bot:", data.reply);
    hapusTyping();
    tampilkanPesan(data.reply, "bot");
  } catch (error) {
    hapusTyping();
    tampilkanPesan(`⚠️ Gagal konek ke server atau terjadi error: ${error.message}`, "bot");
  }
}

function formatPesan(teks) {
  teks = teks.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  const lines = teks.split('\n');
  let html = '', inUl = false, inOl = false;

  for (let line of lines) {
    line = line.trim();

    if (/^[-•]\s+/.test(line)) {
      if (!inUl) {
        html += '<ul>';
        inUl = true;
      }
      html += `<li>${line.replace(/^[-•]\s+/, '')}</li>`;
    } else if (/^\d+\.\s+/.test(line)) {
      if (!inOl) {
        html += '<ol>';
        inOl = true;
      }
      html += `<li>${line.replace(/^\d+\.\s+/, '')}</li>`;
    } else {
      if (inUl) { html += '</ul>'; inUl = false; }
      if (inOl) { html += '</ol>'; inOl = false; }
      if (line !== '') html += `<p>${line}</p>`;
    }
  }

  if (inUl) html += '</ul>';
  if (inOl) html += '</ol>';
  return html;
}

function tampilkanPesan(teks, pengirim) {
  console.log("📨", pengirim, teks);
  const chatBox = document.getElementById("chat-box");
  const elemen = document.createElement("div");
  elemen.className = pengirim;
  elemen.innerHTML = (pengirim === 'bot') ? teks : formatPesan(teks);
  chatBox.appendChild(elemen);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function tampilkanTyping() {
  const chatBox = document.getElementById("chat-box");
  const bubble = document.createElement("div");
  bubble.className = "bot typing";
  bubble.id = "typing-bubble";
  bubble.innerHTML = "<span></span><span></span><span></span>";
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function hapusTyping() {
  const bubble = document.getElementById("typing-bubble");
  if (bubble) bubble.remove();
}

document.getElementById("attachBtn").addEventListener("click", () => {
  document.getElementById("fileInput").click();
});

document.getElementById("pesan").addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    kirim();
  }
});

document.getElementById("clearChatBtn").addEventListener("click", async () => {
  if (confirm("Yakin mau hapus semua chat?")) {
    const sessionId = getSessionId();
    try {
      await fetch(`${BACKEND_URL}/chats?session_id=${sessionId}`, { method: "DELETE" });
      document.getElementById("chat-box").innerHTML = "";
    } catch (error) {
      tampilkanPesan(`⚠️ Gagal menghapus chat dari server: ${error.message}`, "bot");
    }
  }
});

window.onload = async () => {
  const sessionId = getSessionId();
  document.getElementById("chat-box").innerHTML = "";
  try {
    const res = await fetch(`${BACKEND_URL}/chats?session_id=${sessionId}`);
    const data = await res.json();
    data.forEach(chat => {
      const pengirim = (chat.role === 'assistant') ? 'bot' : 'user';
      tampilkanPesan(chat.content, pengirim);
    });
  } catch (error) {
    tampilkanPesan(`⚠️ Gagal memuat riwayat chat dari server: ${error.message}`, "bot");
  }
};
