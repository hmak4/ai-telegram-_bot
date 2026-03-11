import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
import yt_dlp
import qrcode
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
import openai
from dotenv import load_dotenv
import tempfile
import requests
import speech_recognition as sr
from io import BytesIO

# ================= ENV LOAD =================
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")  # int
GROUP_INVITE_LINK = os.environ.get("GROUP_INVITE_LINK", "https://t.me/+yourgroup")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable not set!")
if not GROUP_CHAT_ID:
    raise ValueError("❌ GROUP_CHAT_ID environment variable not set!")
try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("❌ GROUP_CHAT_ID must be integer!")

# ================= LOGGING =================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= CONSTANTS =================
DOWNLOAD_PATH = "./downloads"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)
CHAT_MEMORY = {}  # user_id -> previous messages

# ================= HELPERS =================
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is in the group"""
    try:
        member = await context.bot.get_chat_member(GROUP_CHAT_ID, update.effective_user.id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update, context):
        keyboard = [[InlineKeyboardButton("Join Group", url=GROUP_INVITE_LINK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ You must join the group first.", reply_markup=reply_markup)
        return
    await update.message.reply_text(
        "👋 Welcome! Send a video link, text, PDF, or /draw prompt."
    )

# ================= AI CHAT =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text:
        return

    if user_id not in CHAT_MEMORY:
        CHAT_MEMORY[user_id] = []

    CHAT_MEMORY[user_id].append(f"User: {text}")

    # Send to OpenAI/Groq AI (replace OPENAI_API_KEY in env)
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": text}] + [{"role": "system", "content": m} for m in CHAT_MEMORY[user_id][-5:]]
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"❌ AI Error: {str(e)}"

    CHAT_MEMORY[user_id].append(f"Bot: {reply}")
    await update.message.reply_text(reply)

# ================= QR CODE =================
async def qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /qr <text>")
        return
    text = " ".join(context.args)
    img = qrcode.make(text)
    with BytesIO() as bio:
        img.save(bio, format="PNG")
        bio.seek(0)
        await update.message.reply_photo(bio, caption=f"QR Code for: {text}")

# ================= IMAGE GENERATE =================
async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /draw <prompt>")
        return
    prompt = " ".join(context.args)
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    try:
        r = openai.Image.create(prompt=prompt, n=1, size="1024x1024")
        img_url = r['data'][0]['url']
        await update.message.reply_photo(img_url, caption=f"Generated Image for: {prompt}")
    except Exception as e:
        await update.message.reply_text(f"❌ Image Error: {str(e)}")

# ================= YouTube Transcript =================
async def youtube_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'writeautomaticsub': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get("automatic_captions") or {}
            caption = list(subs.values())[0][0]["text"] if subs else "No captions found."
        await update.message.reply_text(f"📄 Summary:\n{caption[:1000]}...")
    except Exception as e:
        await update.message.reply_text(f"❌ YouTube Error: {str(e)}")

# ================= VOICE MESSAGE =================
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    file_path = os.path.join(tempfile.gettempdir(), "voice.ogg")
    await file.download_to_drive(file_path)
    r = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = r.record(source)
        try:
            text = r.recognize_whisper(audio)  # use OpenAI Whisper or speech_recognition
            await update.message.reply_text(f"🎤 You said: {text}")
            # AI Chat with text
            update.message.text = text
            await chat(update, context)
        except Exception as e:
            await update.message.reply_text(f"❌ Voice Error: {str(e)}")

# ================= MAIN =================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("qr", qr))
    application.add_handler(CommandHandler("draw", draw))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    application.add_handler(MessageHandler(filters.Regex(r"^https?://(www\.)?(youtube\.com|youtu\.be)/"), youtube_summary))

    print("🤖 Bot running...")
    application.run_polling()

if __name__ == "__main__":
    main()
