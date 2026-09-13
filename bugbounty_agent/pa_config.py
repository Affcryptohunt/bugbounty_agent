"""
Fill in your own values below, then save this file. That's the entire
setup — no other file needs editing.
"""

TELEGRAM_BOT_TOKEN = "PASTE_YOUR_BOTFATHER_TOKEN_HERE"

# Your numeric Telegram user ID (from @userinfobot). Only this ID can use
# the bot — everyone else's messages are silently ignored.
TELEGRAM_ALLOWED_USER_IDS = {111111111}  # replace with your real ID

# Make this any random string of your own choosing (letters/numbers,
# no spaces) — it's used as a secret part of your webhook URL so random
# internet traffic can't hit your bot's endpoint. Change it to something
# only you know.
WEBHOOK_SECRET = "change-this-to-something-random-123"

# Optional: paste your Anthropic API key here to enable synthesized /ask
# answers and polished /report text. Leave as None to skip that.
ANTHROPIC_API_KEY = None
