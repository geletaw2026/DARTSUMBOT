import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from google import genai

# ---------------------------------------------------------
# RENDER FREE TIER HEALTH CHECK SERVER
# ---------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Dart Exec Bot is active and healthy!")
        
    def log_message(self, format, *args):
        # Suppress noisy HTTP access logs in terminal
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Start the health check server in a background thread immediately
threading.Thread(target=run_health_check_server, daemon=True).start()

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Error: TELEGRAM_BOT_TOKEN and GEMINI_API_KEY environment variables are missing.")

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = genai.Client()

PROMPT_TEMPLATE = """
You are an expert Construction Project Manager at Dart Engineering Trading PLC.
Analyze the attached scanned construction document (PDF or Image) and extract the essential facts.
Generate an executive briefing tailored for high-level decision makers (General Managers, Client Directors).

Structure your output exactly as follows using clean Markdown formatting:

📱 **[Dart Exec Brief] Project: [Extract Project Name or 'General Site Notice']**

📄 **Doc Ref & Date:** [Document Reference Number & Official Date]
👥 **Parties Involved:** [Sender] ➔ [Receiver]

🔹 **Subject / Core Issue:** 
[Write a concise 1-2 sentence plain-language explanation of the issue]

⚠️ **Critical Path / Schedule Impact:** 
[Identify specific day delays, affected activities, or critical path risk]

💰 **Cost / Financial Impact:** 
[Detail any immediate or potential variations, claims, or budget risks]

🎯 **Action Needed (GM / Director):** 
[Specify the precise executive decision or instruction required]

Keep the summary direct, actionable, and strictly under 150 words.
"""

# ---------------------------------------------------------
# HANDLERS
# ---------------------------------------------------------

# 1. Handle /start and /help commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 **Welcome to the Dart Engineering Executive Brief Bot!**\n\n"
        "Send or upload any scanned construction document (**PDF or Photo/Image**) "
        "and I will automatically generate a concise executive brief for project decision-makers."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# 2. Handle Document & Photo Scans
@bot.message_handler(content_types=['document', 'photo'])
def handle_incoming_scan(message):
    bot.reply_to(message, "⏳ *Dart AI Assistant:* Processing scanned document... Please wait.", parse_mode="Markdown")
    temp_path = None

    try:
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            ext = ".jpg"
        else:
            file_info = bot.get_file(message.document.file_id)
            ext = os.path.splitext(file_info.file_path)[1] or ".pdf"

        downloaded_file = bot.download_file(file_info.file_path)
        temp_path = f"temp_scan{ext}"
        
        with open(temp_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Upload file to Gemini File API
        uploaded_file = client.files.upload(file=temp_path)

        # Generate response using Gemini 3.8 Flash
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[uploaded_file, PROMPT_TEMPLATE]
        )

        bot.send_message(message.chat.id, response.text, parse_mode="Markdown")

        # Cleanup remote file
        client.files.delete(name=uploaded_file.name)

    except Exception as e:
        bot.reply_to(message, f"❌ Error processing document: {str(e)}")

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# 3. Handle Regular Text Messages (like "hi")
@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.reply_to(
        message, 
        "ℹ️ *Dart AI:* Please upload or attach a scanned document (PDF or Photo) for analysis.", 
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    print("🚀 Dart Engineering Exec Brief Bot is running securely...")
    bot.infinity_polling()
