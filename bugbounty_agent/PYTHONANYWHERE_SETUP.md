# Deploying the bot on PythonAnywhere (free, no card needed)

This runs the webhook version (`pa_webhook_bot.py`) — same tutor/ask/kb/
ingest features as the Telegram bot, minus recon (PythonAnywhere's free
tier can't run the scanner binaries; use `cli.py recon` on your own machine
for that instead, since it's a one-off task rather than something you need
running 24/7).

## 1. Get your bot token and user ID (same as before)
- Message **@BotFather** on Telegram, send `/newbot`, follow the prompts,
  copy the token it gives you (looks like `123456:ABC-DEF...`).
- Message **@userinfobot**, copy the numeric ID it replies with.

## 2. Create a free PythonAnywhere account
Go to https://www.pythonanywhere.com/ and sign up for the free "Beginner"
account. No card required.

## 3. Upload the project
- On your PythonAnywhere dashboard, open a **Bash console** (Consoles tab
  → Bash).
- Run:
  ```bash
  git clone https://github.com/<your-username>/bugbounty-agent.git
  cd bugbounty-agent
  pip install --user flask requests pypdf python-docx ebooklib beautifulsoup4 youtube-transcript-api
  ```
  (Use whichever GitHub repo URL you created earlier for this project. If
  you'd rather not use GitHub, you can also upload the files directly
  through the "Files" tab.)

## 4. Fill in your config
Open `pa_config.py` in the PythonAnywhere file editor (Files tab, or type
`nano pa_config.py` in the console) and replace:
- `TELEGRAM_BOT_TOKEN` with your real token
- `TELEGRAM_ALLOWED_USER_IDS` with `{your_numeric_id}`
- `WEBHOOK_SECRET` with any random string you make up
- `ANTHROPIC_API_KEY` — optional, paste your key as a string, or leave `None`

Save the file.

## 5. Create the web app
- Go to the **Web** tab → "Add a new web app" → pick your free domain →
  choose **Flask** → choose the Python version matching your console.
- When it asks for the Flask app file, point it at
  `/home/<your-username>/bugbounty-agent/pa_webhook_bot.py`.
- In the **Code** section of the Web tab, make sure "Source code" and
  "Working directory" both point to your `bugbounty-agent` folder.
- Click the green **Reload** button at the top of the Web tab.

Your bot's webhook URL is now:
`https://<your-username>.pythonanywhere.com/webhook/<your WEBHOOK_SECRET>`

## 6. Tell Telegram to use your webhook
Back in the Bash console, run (replace both placeholders):
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<your-username>.pythonanywhere.com/webhook/<YOUR_WEBHOOK_SECRET>"
```
You should see `{"ok":true,"result":true,...}` in the response.

## 7. Test it
Open Telegram, message your bot: `/start`. You should get the command list
back. Try `/tutor rules` and `/ask <anything>` to confirm it's live.

## Keeping it alive
Free PythonAnywhere web apps go idle if you don't log into your
PythonAnywhere account for a while, and free-tier apps have roughly a
1-month expiry that resets each time you log in and hit Reload. Just log
in and click Reload on the Web tab every few weeks — takes 10 seconds.

## If something goes wrong
- Check the **Error log** and **Server log** links on the Web tab — they
  show Python tracebacks if the bot crashed.
- Double check `pa_config.py` has no leftover placeholder text.
- Re-run the `setWebhook` curl command if you ever change your domain or
  secret.
