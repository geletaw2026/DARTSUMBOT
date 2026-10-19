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

# Template 5: General / Other Documents (Meeting Minutes, Specs, Submittals, Memos)
GENERAL_PROMPT = """
You are a Senior Technical Consultant at Dart Engineering Trading PLC.
Analyze the attached miscellaneous construction document (such as Meeting Minutes, Technical Specification, Material Submittal, Drawing Transmittal, or General Memo).

Structure your output exactly as follows using clean Markdown formatting:

📁 **[Dart General Brief] Project: [Extract Project Name or 'General']**

📄 **Doc Title & Date:** [Document Title, Reference & Date]
📌 **Document Classification:** [Meeting Minutes / Tech Specs / Submittal / Transmittal / Other]

📝 **Executive Overview:** 
[Concise 2-sentence summary of what this document covers and its core purpose]

🔍 **Key Technical & Operational Takeaways:** 
[Highlight the most critical data points, decisions made, specifications, or approvals required]

🎯 **Management Action Required:** 
[Specify any follow-up actions, approvals, or reviews needed from leadership]

Keep the briefing clear, well-structured, and executive-ready.
"""

# ---------------------------------------------------------
# 3. TELEGRAM HANDLERS
# ---------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 **Welcome to the Dart Engineering Executive Brief Bot!**\n\n"
        "Simply send or upload any project document (**PDF or Photo**). "
        "The bot will prompt you with interactive buttons to categorize it accurately."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# Handle Document & Photo Uploads -> Present 5 Interactive Options
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

        # Create 5 Interactive Inline Keyboard Options
        markup = InlineKeyboardMarkup()
        markup.row_width = 2
        markup.add(
            InlineKeyboardButton("📱 Letter / Notice", callback_data="type_letter"),
            InlineKeyboardButton("📋 Tender / RFP", callback_data="type_tender"),
            InlineKeyboardButton("⚖️ Claim / Variation", callback_data="type_claim"),
            InlineKeyboardButton("📊 Progress Report", callback_data="type_report"),
            InlineKeyboardButton("📁 General / Other", callback_data="type_other")
        )

        bot.edit_message_text(
            "✅ **Document uploaded successfully!**\n\nPlease select the document category below:",
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.edit_message_text(f"❌ Error uploading document: {str(e)}", chat_id=message.chat.id, message_id=processing_msg.message_id)

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# Handle Button Clicks (Callbacks) with Real-Time Progress Feedback
@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_doc_type_selection(call):
    chat_id = call.message.chat.id
    uploaded_file = ACTIVE_UPLOADS.get(chat_id)

    if not uploaded_file:
        bot.answer_callback_query(call.id, "⚠️ Session expired or file not found. Please re-upload your document.")
        return

    selection = call.data
    if selection == "type_tender":
        selected_prompt = TENDER_PROMPT
        doc_label = "Tender Brief"
    elif selection == "type_claim":
        selected_prompt = CLAIM_PROMPT
        doc_label = "Claim Analysis"
    elif selection == "type_report":
        selected_prompt = REPORT_PROMPT
        doc_label = "Progress Summary"
    elif selection == "type_other":
        selected_prompt = GENERAL_PROMPT
        doc_label = "General Brief"
    else:
        selected_prompt = LETTER_PROMPT
        doc_label = "Letter Brief"

    bot.answer_callback_query(call.id, f"Processing {doc_label}...")
    
    # Provide immediate user feedback while Gemini reads pages
    bot.edit_message_text(
        f"🔍 *Dart AI Assistant:* Reading document pages and synthesizing {doc_label}...\n*(Larger PDFs may take 10-20 seconds)*", 
        chat_id=chat_id, 
        message_id=call.message.message_id, 
        parse_mode="Markdown"
    )

    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[uploaded_file, selected_prompt]
        )

        bot.send_message(chat_id, response.text, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"❌ Error generating brief: {str(e)}")

    finally:
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
    print("🚀 Dart Engineering Exec Brief Bot is starting up...")
    
    # Clear any lingering Telegram sessions/webhooks to prevent 409 conflicts on restart
    try:
        bot.remove_webhook()
        print("🧹 Cleared existing Telegram webhooks/sessions.")
    except Exception as e:
        print(f"Note on webhook cleanup: {e}")

    print("🚀 Bot is now running polling securely...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10, interval=2, allowed_updates=["message", "callback_query"])
