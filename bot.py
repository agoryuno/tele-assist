import os
import configparser
from io import BytesIO
from datetime import datetime

import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.ext import filters, MessageHandler, PicklePersistence
from telegram.ext import ConversationHandler

from _openai import make_completion, get_response


def _(txt):
    return txt

config = configparser.ConfigParser()
config.read('config.ini')

PERSIST_FILE = config["MAIN"]["PERSIST_FILE"]

BOT_TOKEN = config["MAIN"]["BOT_TOKEN"]

WAITING, END = 1, 2

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text="I'm a bot, please talk to me!")


async def start_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["chat_gpt"] = True
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                      text=_("You are now in conversation with "
                                             "ChatGPT."))
    return WAITING


async def end_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del context.user_data["chat_gpt"]
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text=_("Conversation with ChatGPT ended."))
    return ConversationHandler.END


async def gpt_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_(f"Unknown command:\n {update.message.text}"))
    return WAITING


async def chat_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("chat_gpt", False):
        return ConversationHandler.END
    
    msg = make_completion(update.message.text, 
                          context.user_data.get("gpt_role", None), 
                          context.user_data.get("gpt_context", None))
    print (msg)
    response_txt = get_response(msg)
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=response_txt)
    return WAITING


async def gpt_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gpt_role"] = update.message.text
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_(f"Chat GPT role set to:\n {update.message.text}"))


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.voice.file_id
    new_file = await context.bot.get_file(file_id)
    with BytesIO() as obuff:
        await new_file.download_to_memory(out=obuff)
        print (obuff)


if __name__ == '__main__':

    try:
        os.remove(PERSIST_FILE)
    except FileNotFoundError:
        pass

    persistence = PicklePersistence(PERSIST_FILE)
    application = ApplicationBuilder().persistence(persistence).token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(

        entry_points=[CommandHandler("startgpt", start_gpt)],

        states={
            WAITING: [
                MessageHandler(filters.TEXT, chat_gpt),
                CommandHandler("endgpt", end_gpt)
            ]
        },
        fallbacks=[CommandHandler("endgpt", end_gpt)],
        name="gpt_chat",
        persistent=True,
     )

    
    #start_handler = CommandHandler('start', start)
    #gpt_handler = CommandHandler('gpt', chat_gpt)
    #role_handler = CommandHandler('role', gpt_role)

    #application.add_handler(start_handler)
    #application.add_handler(gpt_handler)
    #application.add_handler(role_handler)

    application.add_handler(conv_handler)

    test_handler = MessageHandler(filters.VOICE, test)
    application.add_handler(test_handler)
    
    application.run_polling()
