from typing import Callable
from telegram import Update
from telegram.ext import ContextTypes


def add_timer(chat_id: int, user_id: int,
                context: ContextTypes.DEFAULT_TYPE, 
                callback_fn: Callable,
                when: int = 15,
                data: dict = None):
    print ("[adding a timer] chat_id:", chat_id, "user_id:", user_id)
    context.job_queue.run_once(
        callback=callback_fn,
        when=when,
        chat_id=chat_id,
        user_id=user_id,
        data=data,
    )