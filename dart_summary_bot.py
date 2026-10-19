import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai

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
# 2. CONFIGURATION & PROMPT TEMPLATES
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Error: TELEGRAM_BOT_TOKEN and GEMINI_API_KEY environment variables are missing.")

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = genai.Client()

# Temporary store to hold uploaded Gemini file references per chat session
ACTIVE_UPLOADS = {}

# Template 1: General Correspondence / Letters
LETTER_PROMPT = """
You are an expert Construction Project Manager at Dart Engineering Trading PLC.
Analyze the attached construction document (Letter, Memo, or Notice) and extract essential facts.

Structure your output exactly as follows using clean Markdown formatting:

📱 **[Dart Exec Brief] Project: [Extract Project Name or 'General Site Notice']**

📄 **Doc Ref & Date:** [Document Reference Number & Official Date]
👥 **Parties Involved:** [Sender] ➔ [Receiver]

🔹 **Subject / Core Issue:** 
[Concise 1-2 sentence explanation of the issue]

⚠️ **Critical Path / Schedule Impact:** 
[Identify day delays, affected activities, or critical path risk]

💰 **Cost / Financial Impact:** 
[Detail variations, claims, or budget risks]

🎯 **Action Needed (GM / Director):** 
[Precise executive decision or instruction required]

Keep the summary direct, actionable, and strictly under 150 words.
"""

# Template 2: Tender Documents / RFPs
TENDER_PROMPT = """
You are an expert Tender & Estimating Manager at Dart Engineering Trading PLC.
Analyze the attached Tender Document, RFP, or Bidding Notice.

Structure your output exactly as follows using clean Markdown formatting:

📋 **[Dart Tender Brief] Project: [Extract Tender Name / Project Title]**

🏢 **Client / Issuing Organization:** [Client Name]
📅 **Key Deadlines:** [Submission Date & Time, Clarification Deadline]
💵 **Financial & Security Terms:** [Bid Bond amount, currency, payment terms]

🏗️ **Scope of Work & Scale:** 
[Briefly describe physical works, location, or major deliverables]

🛡️ **Key Eligibility & Qualification Criteria:** 
[Required licenses, min. annual turnover, similar project experience]

🎯 **Strategic Recommendation / Action:** 
[Initial go/no-go assessment and required next steps for management]

Keep the briefing professional and concise.
"""

# Template 3: Claims & Variation Orders
CLAIM_PROMPT = """
You are an expert Senior Contracts Manager & Claims Consultant at Dart Engineering Trading PLC.
Analyze the attached Claim, Delay Notice, Variation Order, or Dispute Document.

Structure your output exactly as follows using clean Markdown formatting:

⚖️ **[Dart Claim Brief] Project: [Extract Project Name]**

📄 **Ref & Date:** [Document Ref & Date] | **Claim Type:** [EOT / Cost Variation / Disruption / Penalty]
💵 **Financial Claim Amount:** [Requested financial amount / currency]
⏱️ **Time Claim Requested:** [Requested extension of time in calendar days]

🔍 **Contractual Basis & Root Cause:** 
[Summarize contractor's argument, employer's fault, or triggering event citing clauses if mentioned]

⚠️ **Exposure & Risk Analysis:** 
[Evaluate validity, potential liability, liquidated damages risk, and counter-arguments]

🎯 **Recommended Action / Defense Strategy:** 
[Precise steps for management: accept, reject, request particulars, or negotiate]

Keep the analysis sharp, contractual, and executive-focused.
"""

# Template 4: Progress & Site Reports
REPORT_PROMPT = """
You are an expert Resident Engineer / Project Director at Dart Engineering Trading PLC.
Analyze the attached Progress Report, Site Inspection Report, or Technical Evaluation.

Structure your output exactly as follows using clean Markdown formatting:

📊 **[Dart Report Brief] Project: [Extract Project Name]**

📅 **Reporting Period / Date:** [Period covered by the report]
📈 **Overall Physical Progress:** [Completed % vs. Planned %, Schedule Status: On Track / Delayed]

🚧 **Key Accomplishments This Period:** 
[Bullet points of major milestones or site works completed]

⚠️ **Bottlenecks & Critical Site Issues:** 
[Material shortages, equipment breakdowns, weather, design delays, cash flow]

🎯 **Management Action Required:** 
[Interventions required from General Manager or Director to keep project on track]

Keep the brief structured and operations-focused.
"""

# ---------------------------------------------------------
# 3. TELEGRAM HANDLERS
# ---------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 **Welcome to the Dart Engineering Executive Brief Bot!**\n\n"
        "Simply send or upload any project document (**PDF or Photo**). "
        "The bot will immediately ask you to select the document type using interactive buttons so you never have to type commands!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# Handle Document & Photo Uploads -> Present Interactive Options
@bot.message_handler(content_types=['document', 'photo'])
def handle_incoming_scan(message):
    processing_msg = bot.reply_to(message, "⏳ *Dart AI Assistant:* Receiving and uploading document to cloud...", parse_mode="Markdown")
    temp_path = None
    uploaded_file = None

    try:
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            ext = ".jpg"
        else:
            file_info = bot.get_file(message.document.file_id)
            ext = os.path.splitext(file_info.file_path)[1] or ".pdf"

        downloaded_file = bot.download_file(file_info.file_path)
        temp_path = f"temp_scan_{message.chat.id}{ext}"
        
        with open(temp_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Upload file to Gemini File API immediately
        uploaded_file = client.files.upload(file=temp_path)
        
        # Store file reference securely for this chat session
        ACTIVE_UPLOADS[message.chat.id] = uploaded_file

        # Create Interactive Inline Keyboard Options
        markup = InlineKeyboardMarkup()
        markup.row_width = 2
        markup.add(
            InlineKeyboardButton("📱 Letter / Notice", callback_data="type_letter"),
            InlineKeyboardButton("📋 Tender / RFP", callback_data="type_tender"),
            InlineKeyboardButton("⚖️ Claim / Variation", callback_data="type_claim"),
            InlineKeyboardButton("📊 Progress Report", callback_data="type_report")
        )

        bot.edit_message_text(
            "✅ **Document uploaded successfully!**\n\nPlease select the document type below to generate your executive briefing:",
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.edit_message_text(f"❌ Error uploading document: {str(e)}", chat_id=message.chat.id, message_id=processing_msg.message_id)

    finally:
        # Clean up local temporary file instantly
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# Handle Button Clicks (Callbacks)
@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_doc_type_selection(call):
    chat_id = call.message.chat.id
    uploaded_file = ACTIVE_UPLOADS.get(chat_id)

    if not uploaded_file:
        bot.answer_callback_query(call.id, "⚠️ Session expired or file not found. Please re-upload your document.")
        return

    # Determine prompt based on button choice
    selection = call.data
    if selection == "type_tender":
        selected_prompt = TENDER_PROMPT
        doc_label = "Tender Document Brief"
    elif selection == "type_claim":
        selected_prompt = CLAIM_PROMPT
        doc_label = "Claim & Variation Brief"
    elif selection == "type_report":
        selected_prompt = REPORT_PROMPT
        doc_label = "Progress Report Brief"
    else:
        selected_prompt = LETTER_PROMPT
        doc_label = "Executive Letter Brief"

    bot.answer_callback_query(call.id, f"Generating {doc_label}...")
    bot.edit_message_text(f"⏳ *Dart AI Assistant:* Generating {doc_label}...", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown")

    try:
        # Generate analysis using Gemini
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[uploaded_file, selected_prompt]
        )

        bot.send_message(chat_id, response.text, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"❌ Error generating brief: {str(e)}")

    finally:
        # Cleanup remote file from Gemini Cloud and clear cache
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass
        ACTIVE_UPLOADS.pop(chat_id, None)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    bot.reply_to(
        message, 
        "ℹ️ *Dart AI:* Please upload or forward a document (PDF or Photo) to get started.", 
        parse_mode="Markdown"
    )

# ---------------------------------------------------------
# 4. MAIN EXECUTION BLOCK
# ---------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Dart Engineering Exec Brief Bot is running with interactive buttons...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
