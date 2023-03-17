import configparser
import io
import uuid
import os

import openai

import soundfile as sf


config = configparser.ConfigParser()
config.read('config.ini')

CHAT_MODEL = config["MAIN"]["CHAT_MODEL"]
AUDIO_CACHE = ".audio"

openai.api_key = config["MAIN"]["OPENAI_TOKEN"]


def make_completion(prompt, asst=None, context=None, chat_model=CHAT_MODEL):
    asst = "You are a helpful assistant." if asst is None else asst
    messages=[
        {"role": "system", "content": asst}
        ]
    
    if context is not None:
        for msg in context:
            if isinstance(msg, dict) \
                    and msg.get("role", None) is not None \
                    and msg.get("content", None) is not None:
                messages.append(msg)

    messages += [{"role": "user", "content": prompt}]

    return dict(model=chat_model, messages=messages)


def get_response(completion):
    resp = openai.ChatCompletion.create(**completion)
    return resp['choices'][0]['message']['content']


def chatgpt_get_response(completion):
    return get_response(completion)


def convert_to_wav(audio):
    data, samplerate = sf.read(audio)
    wav_buffer = io.BytesIO()
    with sf.SoundFile(wav_buffer, mode='w',
                      channels=1, format='WAV', 
                      samplerate=samplerate,
                      subtype='PCM_16') as wav_file:
        wav_file.write(data)

    return wav_buffer


def save_to_wav(audio, fname):
    data, samplerate = sf.read(audio)
    sf.write(fname, data, samplerate)


def clean_audio_cache(audio_path=AUDIO_CACHE):
    # delete all files in directory
    # `audio_path`
    for file in os.listdir(audio_path):
        try:
            os.remove(os.path.join(audio_path, file))
        except:
            pass


def transcribe_audio(audio):
    audio.seek(0)
    fname = os.path.join(AUDIO_CACHE, f".{str(uuid.uuid4())}.wav")
    save_to_wav(audio, fname)
    
    with open(fname, "rb") as f:
        transcript = openai.Audio.transcribe("whisper-1", f)
    
    try:
        os.remove(fname)
    except:
        pass
    return transcript


def embed_text(text):
    return openai.Embedding.create(input=text,
                            model="text-embedding-ada-002",
                            )["data"][0]['embedding']