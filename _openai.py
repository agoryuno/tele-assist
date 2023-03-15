import configparser

import openai

config = configparser.ConfigParser()
config.read('config.ini')

CHAT_MODEL = config["MAIN"]["CHAT_MODEL"]

openai.api_key = config["MAIN"]["OPENAI_TOKEN"]


def make_completion(prompt, asst=None, context=None, chat_model=CHAT_MODEL):
    asst = "You are a helpful assistant." if asst is None else asst
    messages=[
        {"role": "system", "content": asst},
        {"role": "user", "content": prompt}]
    
    if context is not None:
        for msg in context:
            if isinstance(msg, dict) \
                    and msg.get("role", None) is not None \
                    and msg.get("content", None) is not None:
                messages.append(msg)

        messages += context

    return dict(model=chat_model, messages=messages)


def get_response(completion):
    resp = openai.ChatCompletion.create(**completion)
    return resp['choices'][0]['message']['content']