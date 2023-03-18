from io import BytesIO
import time

from telegram import Update, InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackContext
from telegram.error import TimedOut, BadRequest

from _openai import make_completion, transcribe_audio
from _openai import chatgpt_get_response, embed_text

from utils import get_config, _
from cache import save_message, update_message, get_redis_client
from cache import save_embedding, update_embedding, update_message_id
from timer import add_timer


config = get_config()

GPT_VOICE_CORRECT = 1
GPT_VOICE_ACCEPT = 2

MIN_TEXT_LEN = int(config["VOICE_NOTES"]["MIN_TEXT_LEN"])
APPROVE_TIMEOUT = int (config["VOICE_NOTES"]["APPROVE_TIMEOUT"])


def gpt_correct_template(msg: str):
    asst = "You are an experienced writing editor."
    prompt = ("Correct the grammar and punctuation of the following text that was originally " 
              "transcribed from a voice recording. Try your best to not alter the meaning "
              "in any way. Note that 'chat GPT' refers to you "
              "and should be transcribed as 'ChatGPT'. Here is the text: \n\n"
                f"{msg}"
             )
    comp = make_completion(prompt, asst)
    return comp


async def inline_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        query_msg = int(update.callback_query.data)
    except ValueError:
        print ("Unknown query message: ", update.callback_query.data, type(update.callback_query.data))
    
    if query_msg == GPT_VOICE_CORRECT:
        text_msg = query.message.text
        comp = gpt_correct_template(text_msg)
        correction = chatgpt_get_response(comp)
        
        embedding = await embed_message(correction)

        update_embedding(get_redis_client(),
                         update.effective_user.id,
                         query.message.message_id,
                         correction,
                         embedding)

        update_message(get_redis_client(),
            update.effective_chat.id, 
            query.message.message_id, 
            correction)
        await query.edit_message_text(text=correction)

    elif query_msg == GPT_VOICE_ACCEPT:
        await query.edit_message_reply_markup(reply_markup=None)  
    await query.answer()


def make_correct_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(_("\u270f Edit"), callback_data=GPT_VOICE_CORRECT),
            InlineKeyboardButton(("\u2705 Accept"), callback_data=GPT_VOICE_ACCEPT)
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def remove_approve_buttons(context: CallbackContext):
    data = context.job.data
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    try:
        await context.bot.edit_message_reply_markup(chat_id=chat_id,
                                                message_id=message_id,
                                                reply_markup=None)
    except BadRequest:
        pass


async def embed_message(message_text, pause=2):
    while True:
        try:
            return embed_text(message_text)
        except:
            time.sleep(pause)


async def process_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = get_redis_client()
    min_text_len = MIN_TEXT_LEN
    file_id = update.message.voice.file_id
    print ("Voice message", update.effective_user.id)
    new_file = None
    for _ in range(5):
        try:
            new_file = await context.bot.get_file(file_id)
        except TimedOut:
            continue

    if new_file is None:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=_("Sorry, there was a network error when "
                                              "trying to retrieve the recording. "
                                              "Please try again later."))
        return

    with BytesIO() as obuff:
        await new_file.download_to_memory(out=obuff)
        result = transcribe_audio (obuff)["text"]

    reply_markup = None
    if len(result) >= min_text_len:
        reply_markup = make_correct_keyboard()
    
    embedding = await embed_message(result)
    key, _ = save_embedding(client,
                   update.effective_user.id,
                   result,
                   embedding)

    msg = None
    for _ in range(30):
        try:
            msg = await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f'"{result}"',
                                   reply_markup=reply_markup,)
            break
        except TimedOut:
            time.sleep(2)
            continue

    if not msg:
        print(f"Failed to send to chat {update.effective_chat.id}, message: {result}")

    if reply_markup is not None:
        add_timer(update.effective_chat.id,
                  update.effective_user.id,
                  context,
                  remove_approve_buttons,
                  when=APPROVE_TIMEOUT,
                  data={"message_id": msg.id,
                        "chat_id": update.effective_chat.id,
                        "user_id": update.effective_user.id,
                        }
                  )
    
    if msg is not None:
        save_message(client, 
                     update.effective_chat.id, 
                     msg.message_id, 
                     result,
                     embedding)
        update_message_id(client,
                          key,
                          update.effective_user.id,
                          msg.message_id)
    
    await context.bot.delete_message(chat_id=update.effective_chat.id,
                               message_id=update.message.message_id)