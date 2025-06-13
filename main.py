from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv
import re

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

system_prompt = (
    "Lo adalah Sam-Cuan, konsultan investasi santai buat anak muda dan mahasiswa yang pengen mulai melek finansial.\n"
    "Jawaban lo harus pakai gaya ngobrol santai, tapi tetap rapi, jelas, dan edukatif.\n"
    "Gunakan bullet point, emoji, dan akhiri dengan kalimat penutup yang nyemangatin.\n\n"
    "Contoh:\n"
    "User: 'Gimana cara mulai investasi dari nol?'\n"
    "Assistant: 'Santai, Bro! Nih langkah-langkah buat mulai investasi dari nol:\n"
    "- 💡 Pahami tujuan lo dulu (buat nabung, pensiun, dll)\n"
    "- 📊 Mulai dari instrumen yang aman (kayak reksa dana pasar uang)\n"
    "- 📱 Gunakan aplikasi yang udah terdaftar OJK\n"
    "- 🧠 Belajar dikit-dikit soal risiko & return\n\n"
    "Ingat, investasi itu maraton, bukan sprint. Yang penting mulai dulu, nominal kecil juga gak masalah! 🚀'\n\n"
    "Sekarang bantu jawab pertanyaan user berikut:"
)


# 🧠 Memory percakapan
chat_history = [{"role": "system", "content": system_prompt}]

# 🔧 Format teks ke HTML
def format_reply_to_html(text):
    lines = text.strip().split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        if re.match(r"^\s*[-•]\s", line):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[2:].strip()}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if line.strip() != "":
                html_lines.append(f"<p>{line.strip()}</p>")

    if in_list:
        html_lines.append("</ul>")
    return '\n'.join(html_lines)

@app.get("/")
def root():
    return {"message": "OpenRouter chatbot siap bantu Bos!"}

@app.post("/reset")
def reset_chat():
    global chat_history
    chat_history = [{"role": "system", "content": system_prompt}]
    return {"message": "Percakapan berhasil direset ✅"}

@app.post("/chat")
async def chat(request: Request):
    global chat_history
    data = await request.json()
    user_input = data.get("message", "")
    file_content = data.get("file", "")

    combined_input = user_input
    if file_content:
        combined_input += f"\n\nIni isi file yang dikirim user:\n{file_content}"

    # ➕ Tambahkan input user ke memory
    chat_history.append({"role": "user", "content": combined_input})

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "meta-llama/llama-3.3-8b-instruct:free",
        "messages": chat_history  # 🧠 Kirim semua riwayat
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    result = response.json()

    try:
        reply = result["choices"][0]["message"]["content"]

        # ➕ Tambahkan jawaban ke history
        chat_history.append({"role": "assistant", "content": reply})

        # 🔧 Format ke HTML
        formatted_reply = format_reply_to_html(reply)
        return {"reply": formatted_reply}
    except Exception:
        return {"reply": f"Maaf, error dari OpenRouter: {result}"}

