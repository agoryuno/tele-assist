import os
import re


import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.ext import filters, MessageHandler, PicklePersistence
from telegram.ext import CallbackQueryHandler

from _openai import clean_audio_cache

from utils import get_config, _
from voice_notes import inline_button, process_voice
from cache import get_redis_client, create_index
from search import search_query
from chatgpt import get_start_gpt_kb, start_gpt, chat_gpt, end_gpt


config = get_config()

PERSIST_FILE = config["MAIN"]["PERSIST_FILE"]

BOT_TOKEN = config["MAIN"]["BOT_TOKEN"]



MIN_TEXT_LEN = 150


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def reset_context(context):
    context.user_data["chat_gpt"] = False
    context.user_data["gpt_role"] = None
    context.user_data["gpt_context"] = None
    del context.user_data["chat_gpt"]
    del context.user_data["gpt_role"]
    del context.user_data["gpt_context"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_context(context)

    # just in case we have some leftover data in the temp cache
    clean_audio_cache()

    reply_markup = get_start_gpt_kb()
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_("Hi! I am a personal assitant bot. I "
                                   "keep records for you and help you interact "
                                   "with the world through AIs."), reply_markup=reply_markup)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=_("You can start a conversation with ChatGPT using "
                                          "the button below."))
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=_("There's also no need to type anything (unless you "
                                   "want to). You can send me voice messages and I will transcribe "
                                   "them for you."))


async def gpt_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gpt_role"] = update.message.text
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_(f"Chat GPT role set to:\n {update.message.text}"))


async def start_gpt_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.delete_message(chat_id=update.effective_chat.id, 
                         message_id=update.effective_message.message_id)
    await start_gpt(update, context)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = re.match(r"^/.+?(\s.*|)$", update.message.text)
    if m:
        query = m.group(1).strip()
        if len(query) > 0:
            results = await search_query(update.effective_user.id, query)
            print (results)


async def setup_commands(app):
    await app.bot.set_my_commands([
        ('startgpt', 'Starts a conversation with ChatGPT'),
        ('endgpt', 'Ends a conversation with ChatGPT'),
        ('start', '(Re)starts the bot'),
    ])

async def startup(app):
    await setup_commands(app)
    

if __name__ == '__main__':

    try:
        os.remove(PERSIST_FILE)
    except FileNotFoundError:
        pass

    redis_client = get_redis_client()
    create_index(redis_client)

    persistence = PicklePersistence(PERSIST_FILE)
    application = ApplicationBuilder().persistence(persistence). \
        token(BOT_TOKEN).post_init(startup).build()

    inline_handler = CallbackQueryHandler(inline_button)

    start_handler = CommandHandler("start", start)

    search_handler = CommandHandler("search", search_command)

    endgpt_handler = CommandHandler("endgpt", end_gpt)
    startgpt_handler = CommandHandler("startgpt", start_gpt)
    stopgpt_handler = MessageHandler(filters.Regex(r"^\<Stop ChatGPT\>$"), end_gpt)
    startgpt2_handler = MessageHandler(filters.Regex(r"^\<Start ChatGPT\>$"), start_gpt)
    gptmessage_handler = MessageHandler(filters.TEXT, chat_gpt)

    application.add_handler(start_handler)

    application.add_handler(search_handler)

    application.add_handler(endgpt_handler)
    application.add_handler(stopgpt_handler)
    application.add_handler(startgpt_handler)
    application.add_handler(startgpt2_handler)
    application.add_handler(gptmessage_handler)

    voice_handler = MessageHandler(filters.VOICE, process_voice)
    application.add_handler(voice_handler)
    application.add_handler(inline_handler)
    
    application.run_polling()
