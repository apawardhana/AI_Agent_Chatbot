from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, date
import re
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
 yield db
 finally:
 db.close()

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ChatMessage(Base):
    __tablename__ = "messages"


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

# Define table columns
ChatMessage.id = Column(Integer, primary_key=True, index=True)
ChatMessage.session_id = Column(String, index=True)  # To group messages by session
ChatMessage.role = Column(String)  # 'user' or 'assistant' or 'system'
ChatMessage.content = Column(Text)
ChatMessage.timestamp = Column(DateTime, default=datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

from sqlalchemy.orm import sessionmaker
from fastapi import Depends

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# 🧠 Memory percakapan
# chat_history = [{"role": "system", "content": system_prompt}] # Removed global memory

def chat_message_to_dict(message: ChatMessage):
    return {
        "id": message.id,
 "session_id": message.session_id,
 "role": message.role,
 "content": message.content,
 "timestamp": message.timestamp.isoformat() if isinstance(message.timestamp, (datetime, date)) else None # Handle datetime object
    }

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

@app.post("/chat")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    session_id = data.get("session_id")
 if not session_id:
 return {"reply": "Error: session_id not provided."}
    user_input = data.get("message", "")
    file_content = data.get("file", "")

    combined_input = user_input
    if file_content:
        combined_input += f"\n\nIni isi file yang dikirim user:\n{file_content}"

    # ➕ Tambahkan input user ke memory
 # chat_history.append({"role": "user", "content": combined_input}) # Removed global memory
 user_message = ChatMessage(session_id=session_id, role="user", content=combined_input)
 db.add(user_message)
 db.commit()
 db.refresh(user_message)

 # Fetch previous messages for this session to send as context
 previous_messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
 messages_for_model = [{"role": msg.role, "content": msg.content} for msg in previous_messages]

 # Add the system prompt at the beginning
 messages_for_model.insert(0, {"role": "system", "content": system_prompt})

 # Ensure the last message is the current user message (important for conversational models)
 # This handles the case where file content was added to combined_input
 if messages_for_model[-1]["content"] != combined_input:
        messages_for_model.append({"role": "user", "content": combined_input})

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
    }

    payload = { # Use messages from DB for context
        "model": "meta-llama/llama-3.3-8b-instruct:free",
        "messages": messages_for_model # 🧠 Kirim riwayat dari DB + current user message + system prompt
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    result = response.json()

    try:
        reply = result["choices"][0]["message"]["content"]

        # ➕ Tambahkan jawaban ke history
 # chat_history.append({"role": "assistant", "content": reply}) # Removed global memory
        bot_message = ChatMessage(session_id=session_id, role="assistant", content=reply)
 db.add(bot_message)
 db.commit()
 db.refresh(bot_message)

        # 🔧 Format ke HTML
        formatted_reply = format_reply_to_html(reply)
        return {"reply": formatted_reply}
    except Exception:
        return {"reply": f"Maaf, error dari OpenRouter: {result}"}
    finally:
 db.close() # Ensure session is closed

@app.get("/chats")
def get_chats(session_id: str, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
    return [chat_message_to_dict(msg) for msg in messages]

@app.delete("/chats")
def reset_chat(session_id: str, db: Session = Depends(get_db)):
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return {"message": f"Percakapan untuk sesi {session_id} berhasil dihapus ✅"}

