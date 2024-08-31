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

key="XXX.XXX"

api_key="Bearer "+str(key)



controller = Controller()

parser = argparse.ArgumentParser(description='using flag to decide to use LLM remotely or locally')
parser.add_argument("--remote", "-R", action='store_true',help='Use this flag to use LLM remotely')
args = parser.parse_args()

if args.remote==False:
    llm=Llama(model_path="qwen2-0_5b-instruct-q8_0.gguf")

FIX_PROMPT_TEMPLATE = Template(
    """You are an expert English editor and language model. Your task is to take the following English passage and:

1. Correct any typos and misspellings
2. Optimize the language to make it more formal and native-sounding
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
    with open("/Users/zhouql1978/Documents/Obsidian Vault/remote/notes.md", "a") as file:
        file.write(text+"\n")
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

def on_f9():
    fix_selection(usecase="fix")

def on_f10():
    fix_selection(usecase="translate")

def on_f8():
    write_selection()

def on_f11():
    QA_selection()

with keyboard.GlobalHotKeys({"<103>": on_f11,"<101>": on_f9, "<109>": on_f10,"<100>": on_f8}) as h:
    h.join()