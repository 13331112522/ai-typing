# copied from https://github.com/patrickloeber/ai-typing-assistant/blob/main/main.py
# main changes are to strip out the ollama stuff and replace it with llama-cpp-python to make it truly pythonic

import time
from string import Template
from llama_cpp import Llama
from pynput import keyboard
from pynput.keyboard import Key, Controller
import pyperclip
import requests
import argparse
import os
import ssl
import certifi
from audio_util import  RealtimeAudioChat, WhisperRecorder, play_audio_with_kokoro
# Create SSL context with certifi's certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

key="XXX"

api_key="Bearer "+str(key)

openai_key="XXX"
# ZHIPU_SPEECH_URL = "https://open.bigmodel.cn/api/paas/v3/audio"
# ZHIPU_STT_URL = "https://open.bigmodel.cn/api/paas/v3/audio/asr"
# ZHIPU_TTS_URL = "https://open.bigmodel.cn/api/paas/v3/audio/synthesis"


controller = Controller()

parser = argparse.ArgumentParser(description='using flag to decide to use LLM remotely or locally')
parser.add_argument("--remote", "-R", action='store_true',help='Use this flag to use LLM remotely')
args = parser.parse_args()

if args.remote==False:
    llm=Llama(model_path="qwen2-0_5b-instruct-q8_0.gguf")

FIX_PROMPT_TEMPLATE = Template(
    """You are an expert English editor and language model. Your task is to take the following English passage and:

1. Correct any typos and misspellings
2. Optimize the language to make it more formal and native-sounding as academic journal or paper.
3. Improve sentence structure and flow where needed
4. Ensure proper grammar and punctuation throughout

Please provide the corrected and optimized version of the text, but preserve all new line characters. Here's the passage:


$text

"""
)

TRANSLATE_PROMPT_TEMPLATE = Template(
    """You are a professional translator with expertise in both English and Chinese languages. Your task is to translate the following English text into Chinese, adhering to these guidelines:

1. Provide an accurate and natural-sounding Chinese translation that captures the original meaning and tone.
2. Use Standard Mandarin Chinese (普通话) for the translation.
3. If there are any culturally specific terms or idioms, provide appropriate Chinese equivalents or explanations.
4. Maintain the original formatting and structure where possible.
5. If there are any ambiguous terms or phrases in the English text, provide the most likely translation and add a note explaining the ambiguity.

Original English text:

$text

"""
)

QA_PROMPT_TEMPLATE = Template(
    """
Based on following text, answer the question or follow the instructions: $query

Original Text:

$text
"""
)

KEYWORD_PROMPT_TEMPLATE = Template(
    """
Based on following text, generate 5 key words as tags, start with # and use ; to separate each of them.

Original Text:

$text
"""
)

TRANSCRIPTION_PROMPT_TEMPLATE =  Template(
    """
Please help me reorganize and restructure the following text while preserving its original meaning. I need you to:

1.Maintain all key ideas and content from the original text
2.Improve the logical flow and organization
3.Create clear paragraph breaks and transitions
4.Ensure proper sentence structure and coherence
5.Fix any unclear or ambiguous phrasing
6.Keep the nature of the language, don't do translation and don't add or delete more information.

Here is the text that needs to be reorganized: 
$text
"""
)

def generate_text(prompt, model="glm-4-airX",max_tokens=2000,):
    headers = {
        "Authorization": api_key, 
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt}
            ],
    }
    response = requests.post("https://open.bigmodel.cn/api/paas/v4/chat/completions", headers=headers, json=data)

    return response.json()

def fix_text(text):
    prompt = FIX_PROMPT_TEMPLATE.substitute(text=text)
    if args.remote==True:
        output = generate_text(prompt)
    else:
        output = llm.create_chat_completion(
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
    print(output)

    return output["choices"][0]["message"]["content"].strip()

def translate_text(text):
    prompt = TRANSLATE_PROMPT_TEMPLATE.substitute(text=text)
    if args.remote==True:
        output = generate_text(prompt)
    else:
        output = llm.create_chat_completion(
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
    print(output)
    return output["choices"][0]["message"]["content"].strip()


def fix_current_line(usecase="fix"):
    # macOS short cut to select current line: Cmd+Shift+Left
    controller.press(Key.cmd)
    controller.press(Key.shift)
    controller.press(Key.left)

    controller.release(Key.cmd)
    controller.release(Key.shift)
    controller.release(Key.left)

    if usecase == "fix":
        fix_selection(usecase="fix")
    elif usecase == "translate":
        fix_selection(usecase="translate")


def fix_selection(usecase="fix"):
    # 1. Copy selection to clipboard
    with controller.pressed(Key.cmd):
        controller.tap("c")

    # 2. Get the clipboard string
    time.sleep(0.1)
    text = pyperclip.paste()

    # 3. Fix string
    if not text:
        return
    
    if usecase == "fix":
        fixed_text = fix_text(text)
    elif usecase == "translate":
        fixed_text = translate_text(text)
    if not fixed_text:
        return

    # 4. Paste the fixed string to the clipboard
    pyperclip.copy(fixed_text)
    time.sleep(0.1)

    # 5. Paste the clipboard and replace the selected text
    with controller.pressed(Key.cmd):
        controller.tap("v")

def get_timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def write_selection():
    
    # 1. Copy selection to clipboard
    with controller.pressed(Key.cmd):
        controller.tap("c")

    # 2. Get the clipboard string
    time.sleep(0.1)
    text = pyperclip.paste()
    timestamp = get_timestamp()

    # 3. Generate the key words
    prompt = KEYWORD_PROMPT_TEMPLATE.substitute(text=text)
    if args.remote==True:
        output = generate_text(prompt)
    else:
        output = llm.create_chat_completion(
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
    keywords=output["choices"][0]["message"]["content"].strip()

    # 4. Write to the notes in Obsidian
    with open("/Users/zhouql1978/Documents/Obsidian Vault/remote/notes.md", "a") as file:
        file.write(text+"\n")
        file.write(keywords+"\n")
        file.write(f"--- {timestamp} ---\n\n")
        #file.write("-------------------------\n")

    print("Note saved!")


def transcription_text(text):
    prompt = TRANSCRIPTION_PROMPT_TEMPLATE.substitute(text=text)
    if args.remote==True:
        output = generate_text(prompt)
    else:
        output = llm.create_chat_completion(
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
    

    output_text=output["choices"][0]["message"]["content"].strip()
    print(output_text)

    timestamp = get_timestamp()

    # 3. Generate the key words
    prompt = KEYWORD_PROMPT_TEMPLATE.substitute(text=output_text)
    if args.remote==True:
        output = generate_text(prompt)
    else:
        output = llm.create_chat_completion(
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
    keywords=output["choices"][0]["message"]["content"].strip()
    print(keywords)
    # 4. Write to the notes in Obsidian
    with open("/Users/zhouql1978/Documents/Obsidian Vault/remote/notes.md", "a") as file:
        file.write(output_text+"\n")
        file.write(keywords+"\n")
        file.write(f"--- {timestamp} ---\n\n")
        #file.write("-------------------------\n")

    print("Note saved!")

def QA_selection():
    with controller.pressed(Key.cmd):
        controller.tap("c")

    # 2. Get the clipboard string
    time.sleep(0.1)
    text = pyperclip.paste()
    while True:
        query = input("\nEnter a query: ")
        if query == "exit":
            break
        if query.strip() == "":
            continue
        prompt = QA_PROMPT_TEMPLATE.substitute(text=text,query=query)
        # Get the answer from the chain
        start = time.time()
        res = generate_text(prompt)
        answer= res["choices"][0]["message"]["content"].strip()
        end = time.time()

        # Print the result
        print("\n\n> Question:")
        print(query)
        print(f"\n> Answer (took {round(end - start, 2)} s.):")
        print(answer)


os.environ['SSL_CERT_FILE'] = certifi.where()



def on_f9():
    fix_selection(usecase="fix")

def on_f10():
    fix_selection(usecase="translate")

def on_f8():
    write_selection()

def on_f11():
    QA_selection()

def on_f6():
    if args.remote != True:
        print("You should enable local audio mode!")
    else:
        recorder = WhisperRecorder(api_key=openai_key)
        print("\nPress 'q' to stop recording and translate...")
        trans_text = recorder.start_listening()  # Start listening immediately
        if trans_text:
            transcription_text(trans_text)

def on_f7():
    chat = RealtimeAudioChat(openai_key)
    chat.start()
    
    def on_press(key):
        try:
            if key.char == 'k':
                chat.start_recording()
            elif key.char == 'q':
                chat.stop()
                return False
        except AttributeError:
            pass
            
    def on_release(key):
        try:
            if key.char == 'k':
                chat.stop_recording()
        except AttributeError:
            pass
    
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
        listener.join()

def on_f5():
    # 1. Copy selection to clipboard
    with controller.pressed(Key.cmd):
        controller.tap("c")

    # 2. Get the clipboard string
    time.sleep(0.1)
    text = pyperclip.paste()
    print(text)
    # 3. Play audio with Kokoro
    if text:
        play_audio_with_kokoro(text)
    else:
        print("No text selected to convert to audio.")

def on_f4():
    print("\nExiting...")
    os._exit(0)  # This will stop the program

def main():
    with keyboard.GlobalHotKeys({
        '<103>': on_f11,  # F11 for QA selection
        '<101>': on_f9,   # F9 for fix selection
        '<109>': on_f10,  # F10 for translate selection
        '<100>': on_f8,   # F8 for write selection
        '<98>': on_f7,    # F7 for real-time audio chat
        '<97>': on_f6,    # F6 for transcription
        '<96>': on_f5,    # F5 for converting selected text to audio
        '<95>': on_f4     # fn+F4 for exit
    }) as h:
        h.join()

if __name__ == "__main__":
    main() 