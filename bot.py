import os
import configparser
import asyncio

from datetime import datetime

import logging

from telegram import Update, InlineKeyboardMarkup
from telegram import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.ext import filters, MessageHandler, PicklePersistence
from telegram.ext import ConversationHandler, CallbackQueryHandler

from _openai import make_completion
from _openai import clean_audio_cache, chatgpt_get_response

from utils import get_config, _
from voice_notes import inline_button, process_voice
from cache import get_redis_client


config = get_config()

PERSIST_FILE = config["MAIN"]["PERSIST_FILE"]

BOT_TOKEN = config["MAIN"]["BOT_TOKEN"]

WAITING, END = 1, 2

MIN_TEXT_LEN = 150


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def refresh_ui(context):
    if not context.user_data.get("chat_gpt", False):
        return get_start_gpt_kb()
    return get_stop_gpt_kb()


def reset_context(context):
    context.user_data["chat_gpt"] = False
    context.user_data["gpt_role"] = None
    context.user_data["gpt_context"] = None
    del context.user_data["chat_gpt"]
    del context.user_data["gpt_role"]
    del context.user_data["gpt_context"]


def get_stop_gpt_kb():
    keyboard = [
        [
            KeyboardButton("<Stop ChatGPT>"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_start_gpt_kb():
    keyboard = [
        [
            KeyboardButton("<Start ChatGPT>"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_context(context)

    # just in case we have some leftover data in the temp cache
    clean_audio_cache()

    reply_markup = get_start_gpt_kb()
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_("Hi! I am a personal assitant bot. I "
                                   "keep records for you and help you interact "
                                   "with AIs."), reply_markup=reply_markup)


async def start_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("chat_gpt"):
        await context.bot.send_message(chat_id=update.effective_chat.id, 
                                       text=_("You are already in conversation "
                                              "with ChatGPT."),
                                       reply_markup=refresh_ui(context),
                                       )
        return WAITING

    context.user_data["chat_gpt"] = True

    reply_markup = get_stop_gpt_kb()
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=_("You are now in conversation with "
                                             "ChatGPT."),
                                   reply_markup=reply_markup)
    return WAITING


async def end_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("chat_gpt", False):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=_("You are not in conversation with "
                                               "ChatGPT."),
                                       reply_markup=refresh_ui(context),
                                       )
        return
    reply_markup = get_start_gpt_kb()
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=_("Conversation with ChatGPT ended."),
                                   reply_markup=reply_markup
                                  )
    return ConversationHandler.END


async def gpt_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_(f"Unknown command:\n {update.message.text}"),
                                   reply_markup=refresh_ui(context),
                                   )
    return WAITING


async def chat_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("chat_gpt", False):
        return ConversationHandler.END
    
    reply_markup = get_stop_gpt_kb()
    msg = make_completion(update.message.text, 
                          context.user_data.get("gpt_role", None), 
                          context.user_data.get("gpt_context", None))
    response_txt = chatgpt_get_response(msg)
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=response_txt,
                                   reply_markup=reply_markup)
    return WAITING


async def gpt_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gpt_role"] = update.message.text
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_(f"Chat GPT role set to:\n {update.message.text}"))


async def start_gpt_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.delete_message(chat_id=update.effective_chat.id, 
                         message_id=update.effective_message.message_id)
    await start_gpt(update, context)


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

    cache = get_redis_client()

    persistence = PicklePersistence(PERSIST_FILE)
    application = ApplicationBuilder().persistence(persistence). \
        token(BOT_TOKEN).post_init(startup).build()

    inline_handler = CallbackQueryHandler(inline_button)

    start_handler = CommandHandler("start", start)

    endgpt_handler = CommandHandler("endgpt", end_gpt)
    startgpt_handler = CommandHandler("startgpt", start_gpt)
    stopgpt_handler = MessageHandler(filters.Regex(r"^\<Stop ChatGPT\>$"), end_gpt)
    startgpt2_handler = MessageHandler(filters.Regex(r"^\<Start ChatGPT\>$"), start_gpt)
    gptmessage_handler = MessageHandler(filters.TEXT, chat_gpt)

    application.add_handler(start_handler)
    application.add_handler(endgpt_handler)
    application.add_handler(stopgpt_handler)
    application.add_handler(startgpt_handler)
    application.add_handler(startgpt2_handler)
    application.add_handler(gptmessage_handler)

    voice_handler = MessageHandler(filters.VOICE, process_voice)
    application.add_handler(voice_handler)
    application.add_handler(inline_handler)
    
    application.run_polling()
