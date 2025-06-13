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
    const speechResult = event.results[0][0].transcript;
    input.value = speechResult;
    micBtn.classList.remove('listening');
    input.focus();
  };

  recognition.onerror = () => micBtn.classList.remove('listening');
  recognition.onend = () => micBtn.classList.remove('listening');
} else {
  document.getElementById('micBtn').style.display = 'none';
}

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
  if (file) {
  const reader = new FileReader();
  reader.onload = async () => {
    fileText = reader.result;

    // Tambahkan preview file ke chat (nama + ikon)
    tampilkanPesan(`<strong>📎 ${file.name}</strong>`, "user");

    await kirimKeBackend(pesan, fileText);
  };
  reader.readAsText(file);
} else {
  await kirimKeBackend(pesan, fileText);
}

}

async function kirimKeBackend(message, fileText) {
  tampilkanTyping();

  try {
    const res = await fetch("http://192.168.20.111:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, file: fileText })
    });
    const data = await res.json();
    hapusTyping();
    tampilkanPesan(data.reply, "bot");
  } catch {
    hapusTyping();
    tampilkanPesan("⚠️ Gagal konek ke server.", "bot");
  }
}

function formatPesan(teks) {
  // Ubah **teks** jadi <strong>
  teks = teks.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // Bagi baris per baris
  const lines = teks.split('\n');
  let html = '';
  let inUl = false;
  let inOl = false;

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
      if (inUl) {
        html += '</ul>';
        inUl = false;
      }
      if (inOl) {
        html += '</ol>';
        inOl = false;
      }
      if (line !== '') {
        html += `<p>${line}</p>`;
      }
    }
  }

  if (inUl) html += '</ul>';
  if (inOl) html += '</ol>';

  return html;
}

function tampilkanPesan(teks, pengirim) {
  const chatBox = document.getElementById("chat-box");
  const elemen = document.createElement("div");
  elemen.className = pengirim;
  elemen.innerHTML = formatPesan(teks);
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
    try {
      await fetch("http://192.168.20.111:8000/chats", { method: "DELETE" });
      document.getElementById("chat-box").innerHTML = "";
    } catch {
      tampilkanPesan("⚠️ Gagal hapus chat dari server.", "bot");
    }
  }
});

window.onload = async () => {
  try {
    const res = await fetch("http://localhost:8000/chats");
    const data = await res.json();
    data.forEach(chat => {
      tampilkanPesan(chat.user, "user");
      tampilkanPesan(chat.bot, "bot");
    });
  } catch {
    console.warn("Gagal ambil riwayat");
  }
};