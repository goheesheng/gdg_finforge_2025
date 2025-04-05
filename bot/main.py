from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from nlp_processor import NLPProcessor
import os
from dotenv import load_dotenv
load_dotenv()

nlp_processor = NLPProcessor()

async def handle_message(update: Update, context):
    try:
        user_msg = update.message.text
        intent = nlp_processor.parse_command(user_msg)
        handler = health_handler()
        
        if intent['action'] == 'swap':
            tx_data = await handler.execute_swap(intent)
        elif intent['action'] == 'stake':
            tx_data = await handler.execute_stake(intent)
        else:
            await update.message.reply_text("Unsupported action")
            return

        # deep_link = generate_wallet_deeplink(tx_data)
        
        await update.message.reply_text(
            f"✅ Confirm {intent['action'].title()}:\n"
            f"-  Amount: {intent['amount']} {intent['from_token']}\n"
            f"-  To: {intent.get('to_token', 'stETH')}\n"
            f"-  From: {intent.get('from_address', '0x6c82Af04ffCbEE005120DC53267F0696bD46f56b')}\n" # Default if not specified
            # f"🔗 Approve: {deep_link}"
        )

        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
