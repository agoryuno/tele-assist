from io import BytesIO

from telegram import Update, InlineKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TimedOut

from _openai import make_completion, transcribe_audio
from _openai import chatgpt_get_response

from utils import get_config, _

config = get_config()

GPT_VOICE_CORRECT = config["VOICE_NOTES"]["GPT_VOICE_CORRECT"]
MIN_TEXT_LEN = config["VOICE_NOTES"]["MIN_TEXT_LEN"]



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
    query_msg = update.callback_query.data
    
    if query_msg == GPT_VOICE_CORRECT:
        text_msg = query.message.text
        comp = gpt_correct_template(text_msg)
        correction = chatgpt_get_response(comp)
        
        await query.edit_message_text(text=correction)
        #await query.edit_message_reply_markup(reply_markup=None)
        await query.answer()


def make_correct_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(_("Correct"), callback_data=GPT_VOICE_CORRECT),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)



async def process_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    min_text_len = MIN_TEXT_LEN
    file_id = update.message.voice.file_id
    
    new_file = None
    for i in range(5):
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

    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f'"{result}"',
                                   reply_markup=reply_markup,)
    
    await context.bot.delete_message(chat_id=update.effective_chat.id,
                               message_id=update.message.message_id)