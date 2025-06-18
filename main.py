from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
import pandas as pd
import re

# 🔧 Load ENV
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat.db")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 🗄️ Setup DB
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

# 📄 FAQ
faq_df = pd.read_excel("data/FAQ.xlsx")
faq_df.columns = faq_df.columns.str.strip().str.upper()
faq_df = faq_df.head(100)
faq_text = "\n".join(
    f"Q: {row['PERTANYAAN']}\nA: {row['JAWABAN']}" for _, row in faq_df.iterrows()
)

system_prompt = (
    "Lo adalah Admin dari Kampus Gratis.\n"
    "Berikut beberapa pertanyaan dan jawaban yang sering ditanyain:\n\n"
    f"{faq_text}\n\n"
    "Sekarang bantu jawab pertanyaan user berikut:"
)

# 🔧 Format teks ke HTML
def format_reply_to_html(text):
    lines = text.strip().split('\n')
    html_lines, in_list = [], False

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
            if line.strip():
                html_lines.append(f"<p>{line.strip()}</p>")

    if in_list:
        html_lines.append("</ul>")
    return '\n'.join(html_lines)

# 🚀 FastAPI App
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    combined_input = user_input + (f"\n\nIsi file:\n{file_content}" if file_content else "")

    # Simpan user message
    user_msg = ChatMessage(session_id=session_id, role="user", content=combined_input)
    db.add(user_msg)
    db.commit()

    # Ambil semua histori chat
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
    messages_for_model = [{"role": msg.role, "content": msg.content} for msg in messages]
    messages_for_model.insert(0, {"role": "system", "content": system_prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "meta-llama/llama-3.3-8b-instruct:free",
        "messages": messages_for_model
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        reply = result["choices"][0]["message"]["content"]

        # Simpan reply ke DB
        bot_msg = ChatMessage(session_id=session_id, role="assistant", content=reply)
        db.add(bot_msg)
        db.commit()

        return {"reply": format_reply_to_html(reply)}

    except Exception as e:
        return {"reply": f"⚠️ Gagal dapetin jawaban dari OpenRouter: {e}"}

@app.get("/chats")
def get_chats(session_id: str, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
    return [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in messages]

@app.delete("/chats")
def reset_chat(session_id: str, db: Session = Depends(get_db)):
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return {"message": f"Percakapan untuk sesi {session_id} berhasil dihapus ✅"}