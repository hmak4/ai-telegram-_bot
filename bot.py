import os
import asyncio
import logging
import requests
import speech_recognition as sr
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import qrcode
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
from dotenv import load_dotenv

# ================= Environment =================
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not set")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not set")
if not GROUP_CHAT_ID:
    raise ValueError("❌ GROUP_CHAT_ID not set")
GROUP_CHAT_ID = int(GROUP_CHAT_ID)

openai.api_key = OPENAI_API_KEY

# ================= Logging =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= Helper Functions =================
async def is_group_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(GROUP_CHAT_ID, update.effective_user.id)
        return member.status in ["administrator", "creator", "member"]
    except Exception as e:
        logger.error(f"Group check error: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await is_group_member(update, context)
    if not member:
        await update.message.reply_text(f"❌ You must join the group first: t.me/+xyz123")
        return
    await update.message.reply_text("🤖 AI Bot Ready! Send me a message, voice note, or /draw command.")

# ================= Voice-to-Text =================
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await is_group_member(update, context)
    if not member:
        await update.message.reply_text("❌ You must join the group first!")
        return

    file = await update.message.voice.get_file()
    path = f"temp_{update.message.from_user.id}.ogg"
    await file.download_to_drive(path)

    r = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio = r.record(source)
        try:
            text = r.recognize_google(audio)
            await update.message.reply_text(f"🎤 You said:\n{text}")
        except Exception as e:
            await update.message.reply_text(f"❌ Could not recognize audio: {e}")
    os.remove(path)

# ================= Chat with AI =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await is_group_member(update, context)
    if not member:
        await update.message.reply_text("❌ You must join the group first!")
        return
    prompt = update.message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response["choices"][0]["message"]["content"]
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"❌ AI Error: {str(e)}")

# ================= Image Generate =================
async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await is_group_member(update, context)
    if not member:
        await update.message.reply_text("❌ You must join the group first!")
        return
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("❌ Usage: /draw <prompt>")
        return
    try:
        response = openai.Image.create(prompt=prompt, n=1, size="512x512")
        image_url = response['data'][0]['url']
        await update.message.reply_photo(image_url)
    except Exception as e:
        await update.message.reply_text(f"❌ Image AI Error: {str(e)}")

# ================= QR Code =================
async def qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await is_group_member(update, context)
    if not member:
        await update.message.reply_text("❌ You must join the group first!")
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Usage: /qr <text>")
        return
    qr_img = qrcode.make(text)
    path = f"qr_{update.message.from_user.id}.png"
    qr_img.save(path)
    with open(path, "rb") as f:
        await update.message.reply_photo(f)
    os.remove(path)

# ================= Main =================
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    application.add_handler(CommandHandler("draw", draw))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("🤖 Bot running...")
    application.run_polling()

if __name__ == "__main__":
    main()
