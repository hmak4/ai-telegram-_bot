import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import requests
from dotenv import load_dotenv
import qrcode
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
import speech_recognition as sr
from io import BytesIO

# -------------------- Environment --------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ALLOWED_GROUP_ID = int(os.environ.get("ALLOWED_GROUP_ID", 0))

if not BOT_TOKEN or not GROQ_API_KEY or not ALLOWED_GROUP_ID:
    raise ValueError("❌ Environment variables not set! Check .env or GitHub Secrets.")

# -------------------- Logging --------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- Group Verify --------------------
async def is_member(update: Update):
    try:
        member = await update.effective_chat.get_member(update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# -------------------- AI Chat (Grok) --------------------
async def ai_chat(user_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": user_text}]
    }
    r = requests.post(url, headers=headers, json=data)
    result = r.json()
    if "choices" not in result:
        return f"❌ API Error: {result}"
    return result["choices"][0]["message"]["content"]

# -------------------- Voice-to-Text --------------------
async def voice_to_text(file_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio)
    except Exception:
        return "❌ Could not recognize audio."

# -------------------- QR Generator --------------------
def generate_qr(data: str) -> BytesIO:
    qr_img = qrcode.make(data)
    bio = BytesIO()
    qr_img.save(bio, format='PNG')
    bio.seek(0)
    return bio

# -------------------- Telegram Handlers --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 স্বাগতম! আমি AI Telegram Bot।\n"
        "AI Chat, Voice-to-Text, QR, PDF Utilities সব করতে পারি।"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Group verification
    if update.effective_chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text("❌ Access denied. Join the allowed group first.")
        return
    if not await is_member(update):
        await update.message.reply_text("❌ You must be a member of the group to use the bot.")
        return

    text = update.message.text
    if not text:
        await update.message.reply_text("❌ Please send some text or a file.")
        return

    # Command examples
    if text.startswith("/qr "):
        data = text[4:]
        qr_file = generate_qr(data)
        await update.message.reply_photo(qr_file, caption=f"✅ QR for: {data}")
        return

    # AI Chat fallback
    reply = await ai_chat(text)
    await update.message.reply_text(reply)

# -------------------- Main --------------------
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 AI Telegram Bot running...")
    application.run_polling()

if __name__ == "__main__":
    main()
