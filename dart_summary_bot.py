import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. RENDER FREE TIER HEALTH CHECK SERVER
# ---------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Dart Exec Bot is active and healthy!")
        
    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# ---------------------------------------------------------
# 2. CONFIGURATION & INSTANT EXECUTIVE PROMPT
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Error: TELEGRAM_BOT_TOKEN and GEMINI_API_KEY environment variables are missing.")

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = genai.Client()

EXECUTIVE_PROMPT = """
You are an expert Senior Construction Project Manager and Contracts Consultant at Dart Engineering Trading PLC.
Analyze the attached construction document (Letter, Notice, Claim, Tender, Report, or Memo) and extract essential facts immediately.

Structure your output clearly using plain text formatting with section headers like:

[Dart Brief] Project: [Extract Project Name or 'General Site Notice']

Doc Ref & Date: [Document Reference Number & Official Date]
Parties Involved: [Sender] -> [Receiver]
Document Classification: [Letter / Claim / Report / Tender / Memo / Other]

Subject / Core Issue: 
[Concise 1-2 sentence explanation of the core issue or purpose]

Critical Path / Schedule Impact: 
[Identify day delays, affected site activities, or critical path risk]

Cost / Financial Impact: 
[Detail variations, financial claims, or budget risks]

Action Needed (GM / Director): 
[Precise executive decision or instruction required]

Keep the summary direct, actionable, and strictly under 150 words.
"""

# Helper function to safely send or edit messages as plain text, avoiding all formatting crashes
def safe_send_or_edit(chat_id, text, message_id=None):
    max_length = 4096
    if len(text) <= max_length:
        if message_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text)
    else:
        chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        for idx, chunk in enumerate(chunks):
            if idx == 0 and message_id:
                try:
                    bot.edit_message_text(chunk, chat_id=chat_id, message_id=message_id)
                    continue
                except Exception:
                    pass
            bot.send_message(chat_id, chunk)

# ---------------------------------------------------------
# 3. TELEGRAM HANDLERS WITH BACKGROUND THREADING & RETRY LOGIC
# ---------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Welcome to the Dart Engineering Executive Brief Bot!\n\n"
        "Simply send or upload any construction document (PDF or Photo). "
        "The bot will instantly analyze it and deliver your brief."
    )
    bot.reply_to(message, welcome_text)

def process_document_background(chat_id, message_id, file_id, is_photo, ext):
    temp_path = None
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_path = f"temp_scan_{chat_id}{ext}"
        
        with open(temp_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        with open(temp_path, "rb") as f:
            file_bytes = f.read()

        # Dynamically set correct MIME type based on file extension
        if ext.lower() == ".pdf":
            mime_type = "application/pdf"
        elif ext.lower() in [".png", ".webp"]:
            mime_type = f"image/{ext.lower().strip('.')}"
        else:
            mime_type = "image/jpeg"

        file_part = types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type,
        )

        # Automatic retry loop to handle temporary 503 high-demand spikes gracefully
        response = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[file_part, EXECUTIVE_PROMPT]
                )
                break
            except Exception as api_err:
                if ("503" in str(api_err) or "UNAVAILABLE" in str(api_err)) and attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1)) # Wait 3s, then 6s before retrying
                    continue
                raise api_err

        safe_send_or_edit(chat_id, response.text, message_id=message_id)

    except Exception as e:
        safe_send_or_edit(chat_id, f"Error generating brief: {str(e)}", message_id=message_id)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@bot.message_handler(content_types=['document', 'photo'])
def handle_instant_scan(message):
    processing_msg = bot.reply_to(message, "Dart AI Assistant: Received document. Generating brief...")
    
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        is_photo = True
        ext = ".jpg"
    else:
        file_id = message.document.file_id
        is_photo = False
        doc_name = getattr(message.document, 'file_name', '.pdf') or '.pdf'
        ext = os.path.splitext(doc_name)[1] or ".pdf"

    threading.Thread(
        target=process_document_background,
        args=(message.chat.id, processing_msg.message_id, file_id, is_photo, ext),
        daemon=True
    ).start()

@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.reply_to(
        message, 
        "Dart AI: Please upload or forward a construction document (PDF or Photo) to get an instant brief."
    )

# ---------------------------------------------------------
# 4. MAIN EXECUTION BLOCK
# ---------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Dart Engineering Exec Brief Bot is starting up...")
    time.sleep(5)
    
    try:
        bot.remove_webhook()
        bot.delete_webhook(drop_pending_updates=True)
        print("🧹 Cleared existing Telegram webhooks and pending updates.")
    except Exception as e:
        print(f"Note on webhook cleanup: {e}")

    print("🚀 Bot is running polling with background threading and gemini-2.5-flash stability...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10, interval=3, allowed_updates=["message"])
