# bot.py
import os
import requests
import asyncio
from telegram import Update, InputFile
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv

# ================= Environment =================
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ALLOWED_GROUP_ID = int(os.environ.get("ALLOWED_GROUP_ID", "-1003805314057"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # Groq AI API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # OpenAI API Key (optional)

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable not set!")

# ================= AI Chat Handler =================
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sends a message, bot replies using Groq AI (or fallback OpenAI)"""
    # গ্রুপ চেক
    chat_id = update.effective_chat.id
    if chat_id != ALLOWED_GROUP_ID:
        await update.message.reply_text("❌ You are not allowed to use this bot.")
        return

    user_text = update.message.text

    # Groq AI Request
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": user_text}]
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)
        result = r.json()
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
        else:
            reply = f"❌ AI Error: {result}"
    except Exception as e:
        reply = f"❌ Request failed: {e}"

    await update.message.reply_text(reply)

# ================= Start Command =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 AI Bot is running!\n"
        "Send me a message and I will reply using AI.\n"
        "Supported: Text Chat, Voice-to-Text, Image Generate, PDF/QR Utilities."
    )

# ================= Application =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
