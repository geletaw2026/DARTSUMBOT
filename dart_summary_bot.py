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
def safe_send_or_edit
