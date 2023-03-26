from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram import Update
from telegram.ext import ConversationHandler

from _openai import make_completion, chatgpt_get_response
from utils import _

WAITING, END = 1, 2



def refresh_ui(context):
    if not context.user_data.get("chat_gpt", False):
        return get_start_gpt_kb()
    return get_stop_gpt_kb()


async def gpt_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gpt_role"] = update.message.text
    await context.bot.send_message(chat_id=update.effective_chat.id, 
                                   text=_(f"Chat GPT role set to:\n {update.message.text}"))


async def start_gpt_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.delete_message(chat_id=update.effective_chat.id, 
                         message_id=update.effective_message.message_id)
    await start_gpt(update, context)


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