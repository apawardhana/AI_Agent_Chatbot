from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from dotenv import load_dotenv
import re
import pandas as pd

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

faq_df = pd.read_excel("data/FAQ.xlsx")
faq_df = faq_df.head(20)

faq_text = "\n".join(
    f"Q: {row['PERTANYAAN']}\nA: {row['JAWABAN']}"
    for _, row in faq_df.iterrows()
)

system_prompt = (
    "Lo adalah Admin dari Kampus Gratis.\n"
    "Berikut beberapa pertanyaan dan jawaban yang sering ditanyain:\n\n"
    f"{faq_text}\n\n"
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
    chat_history.append({"role": "user", "content": combined_input})

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "openai/gpt-4.1-nano",
        "messages": chat_history
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    result = response.json()

    try:
        reply = result["choices"][0]["message"]["content"]

        chat_history.append({"role": "user", "content": combined_input})
        if len(chat_history) > 20:
            chat_history = [chat_history[0]] + chat_history[-19:]


        # 🔧 Format ke HTML
        formatted_reply = format_reply_to_html(reply)
        return {"reply": formatted_reply}
    except Exception:
        return {"reply": f"Maaf, error dari OpenRouter: {result}"}

