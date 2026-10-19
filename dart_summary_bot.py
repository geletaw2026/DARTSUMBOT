import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

print("🟢🟢 DART EXEC BRIEF BOT (NATIVE BUTTONS) STARTING 🟢🟢", flush=True)

try:
    import telebot
    from telebot import types
    from google import genai
    print("🟢 All required libraries imported successfully.", flush=True)
except Exception as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}", flush=True)
    sys.exit(1)

# ---------------------------------------------------------
# CONFIGURATION & ENVIRONMENT VARIABLES
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN or GEMINI_API_KEY is missing from environment variables!", flush=True)
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# Temporary storage for pending files waiting for language selection (chat_id -> file_info)
pending_files = {}

# DYNAMIC CONTEXT-AWARE EXECUTIVE PROMPT
EXECUTIVE_PROMPT = """
You are an expert Senior Construction Project Manager and Contracts Consultant at Dart Engineering Trading PLC.
Analyze the attached construction document and dynamically structure your brief based on the DOCUMENT TYPE identified below:

---

### IF TYPE 1: FORMAL LETTER / CONTRACTUAL NOTICE / MEMO
[Dart Brief] Type: Formal Letter / Contractual Notice
Project: [Project Name or 'General Site Notice']
Doc Ref & Date: [Ref No. & Date] | From: [Sender] -> To: [Receiver]

Core Issue: [Concise 1-2 sentence explanation of the main topic/instruction]
Contractual Risk & Deadlines: [Identify legal implications, explicit deadlines, or contractual exposure]
Action Needed (GM / Director): [Precise executive action, reply required, or decision]

---

### IF TYPE 2: CONTRACT CLAIM / EXTENSION OF TIME (EOT) / VARIATION REQUEST
[Dart Brief] Type: Claim / EOT / Variation Request
Project: [Project Name]
Doc Ref & Date: [Ref No. & Date] | From: [Contractor/Consultant] -> To: [Client/Engineer]

Claim Summary: [Key event causing delay or financial variation]
Schedule Impact: [Specific number of delay days claimed & critical path activities affected]
Financial Impact: [Exact cost/amount claimed or price adjustment]
Contract Clause Cited: [e.g., FIDIC Clause 8.4, 13.7, or specific contract clause]
Action Needed (GM / Director): [Recommended response strategy or approval requirement]

---

### IF TYPE 3: SITE PROGRESS REPORT / MONITORING REPORT / MINUTES
[Dart Brief] Type: Site Progress Report / Minutes
Project: [Project Name]
Period / Date: [Reporting Period or Meeting Date]

Current Status: [Planned vs Actual Progress percentage or key milestones achieved]
Critical Bottlenecks: [Material shortfalls, equipment downtime, or site delays]
Safety / Quality Concerns: [Major non-conformances (NCRs) or safety incidents recorded]
Action Needed (GM / Director): [Key resource allocation or operational instruction]

---

### IF TYPE 4: TENDER / BOQ / COMMERCIAL QUOTATION
[Dart Brief] Type: Tender / BOQ / Commercial Document
Project: [Project / Client Name]
Doc Date: [Date]

Scope Summary: [Core work packages or equipment being quoted]
Commercial Terms: [Total value, unit rates, payment milestones, or validity period]
Key Risks / Omissions: [Excluded work scope, price escalation clauses, or unusual conditions]
Action Needed (GM / Director): [Pricing decision, bid submission approval, or negotiation point]

---

GENERAL RULES:
1. Auto-select ONLY ONE relevant structure template from above based on the document contents.
2. Maintain plain-text formatting (no raw Markdown headers like ## or ** formatting that break plain text).
3. Keep the overall briefing direct, actionable, and under 180 words.
"""

# ---------------------------------------------------------
# 1. HEALTH CHECK SERVER (Required for Cloud Hosting / Render)
# ---------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Dart Exec Bot is active and healthy!")
        
    def log_message(self, format, *args):
        return

def run_health_check_server():
    try:
        port = int(os.environ.get("PORT", 10000))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health check server note: {e}", flush=True)

threading.Thread(target=run_health_check_server, daemon=True).start()

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
# 2. TELEGRAM HANDLERS
# ---------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    print(f"📥 Received /start command from user ID: {message.from_user.id}", flush=True)
    welcome_text = (
        "Welcome to the Dart Engineering Executive Brief Bot!\n\n"
        "Simply upload or forward any construction document (PDF or Photo).\n"
        "You will instantly be prompted with native language buttons to select your response format before generation."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['document', 'photo'])
def handle_incoming_document(message):
    print(f"📥 Received incoming file from user ID: {message.from_user.id}", flush=True)
    
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        ext = ".jpg"
    else:
        file_id = message.document.file_id
        doc_name = getattr(message.document, 'file_name', '.pdf') or '.pdf'
        ext = os.path.splitext(doc_name)[1] or ".pdf"

    # Save pending file reference for this chat
    pending_files[message.chat.id] = {'file_id': file_id, 'ext': ext}

    # Create inline keyboard with native localized button text
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("English", callback_data="lang_en"),
        types.InlineKeyboardButton("አማርኛ", callback_data="lang_am"),
        types.InlineKeyboardButton("中文", callback_data="lang_zh")
    )

    bot.reply_to(
        message, 
        "📄 **Construction Document Received!**\n"
        "Select language / ቋንቋ ይምረጡ / 请选择语言:", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def handle_language_selection(call):
    chat_id = call.message.chat.id
    lang_code = call.data.split('_')[1]
    lang_names = {'en': 'English', 'am': 'Amharic (አማርኛ)', 'zh': 'Chinese (中文)'}
    selected_lang_name = lang_names.get(lang_code, 'English')

    if chat_id not in pending_files:
        bot.answer_callback_query(call.id, "Session expired or file missing. Please re-upload your document.")
        return

    file_info = pending_files.pop(chat_id)
    
    bot.answer_callback_query(call.id, f"Selected: {selected_lang_name}")
    
    # Edit the prompt message to show processing status in native style
    status_texts = {
        'en': "⚙️ Dart AI: Analyzing document & generating executive brief in English (Model: gemini-3.8-flash)...",
        'am': "⚙️ ዳርት አርቴፊሻል ኢንተለጀንስ፡ ሰነዱን በመመርመር ላይ እና ማጠቃለያውን በአማርኛ በማዘጋጀት ላይ...",
        'zh': "⚙️ Dart AI: 正在分析文档并以中文生成执行摘要..."
    }
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=status_texts.get(lang_code, status_texts['en']),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # Spawn background processing thread
    threading.Thread(
        target=process_document_background,
        args=(chat_id, call.message.message_id, file_info['file_id'], file_info['ext'], selected_lang_name),
        daemon=True
    ).start()

def process_document_background(chat_id, message_id, file_id, ext, selected_lang_name):
    temp_path = None
    uploaded_file_ref = None
    try:
        print(f"📥 Downloading file from Telegram servers (chat_id: {chat_id})...", flush=True)
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_path = f"temp_scan_{chat_id}{ext}"
        
        with open(temp_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        print(f"☁️ Uploading file to Gemini File API...", flush=True)
        uploaded_file_ref = client.files.upload(file=temp_path)

        # Append language instruction to prompt
        final_prompt = EXECUTIVE_PROMPT + f"\n\nIMPORTANT LANGUAGE INSTRUCTION: Output the entire final briefing strictly in {selected_lang_name}."

        MODEL_NAME = 'gemini-3.8-flash'
        print(f"🤖 Sending request to Gemini (model: {MODEL_NAME}) in language: {selected_lang_name}...", flush=True)
        
        response = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[uploaded_file_ref, final_prompt]
                )
                break
            except Exception as api_err:
                print(f"⚠️ Gemini API attempt {attempt + 1} failed: {api_err}", flush=True)
                if ("503" in str(api_err) or "UNAVAILABLE" in str(api_err) or "429" in str(api_err)) and attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise api_err

        print("✨ Successfully generated localized brief. Sending to Telegram...", flush=True)
        safe_send_or_edit(chat_id, response.text, message_id=message_id)

    except Exception as e:
        print(f"❌ Error in background process: {str(e)}", flush=True)
        safe_send_or_edit(chat_id, f"❌ Error generating brief: {str(e)}", message_id=message_id)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        if uploaded_file_ref:
            try:
                client.files.delete(name=uploaded_file_ref.name)
            except Exception:
                pass

@bot.message_handler(content_types=['text'])
def handle_text(message):
    print(f"💬 Received text message: {message.text}", flush=True)
    bot.reply_to(
        message, 
        "Dart AI: Please upload or forward a construction document (PDF or Photo) to select a language and receive an instant brief."
    )

# ---------------------------------------------------------
# 3. MAIN EXECUTION BLOCK
# ---------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Dart Engineering Exec Brief Bot is starting up...", flush=True)
    time.sleep(2)
    
    try:
        bot.remove_webhook()
        bot.delete_webhook(drop_pending_updates=True)
        print("🧹 Cleared existing Telegram webhooks and pending updates.", flush=True)
    except Exception as e:
        print(f"Note on webhook cleanup: {e}", flush=True)

    print("🚀 Bot is running polling with gemini-3.8-flash...", flush=True)
    bot.infinity_polling(timeout=20, long_polling_timeout=10, interval=3, allowed_updates=["message", "callback_query"])
