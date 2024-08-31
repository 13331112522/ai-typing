# LLaMA Assistant for Mac with remote mode

A simple assistant for Mac that both support `llama-cpp-python` to assist you locally with Qwen0.5-Instruct and remotely with Zhipu GLM-4-airX (easy to extend to other LLMs according to your needs).

## Updating:

1. Add the keyboard shortcut Fn+F11 to initiate a chat with the selected text. You may pose questions about the text or provide instructions, such as translation or optimization, among others. To exit the chat, type EXIT.

2. Add the keyboard shortcut Fn+F8 to allow you to save the selected text into a file as a note at any time. This feature uses Obsidian notes as an example and is particularly convenient for saving important information while browsing the web or reading documents.


## Why?

Because I wanted a more pythonic solution and wanted to build something w/ llama-cpp-python.

Because sometimes purely local mode with llama-cpp-python is not enough, I wanted to use remote model to get better results.

## Setup

Create a virtual environment and follow the steps below.

1. Install llama-cpp-python

`CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python`

Note: If you are on CUDA/ CPU, you can remove the `CMAKE_ARGS="-DGGML_METAL=on"` part and  replace with appropriate cmake args [here](https://llama-cpp-python.readthedocs.io/en/latest/#supported-backends).

2. Install pynput and pyperclip

`pip install pynput pyperclip`

3. Download the model and put it in the same dir as the main.py

qwen2-0_5b-instruct-q8_0.gguf (Change this according to your needs)

4. Run 

python main.py #local mode

python main.py -R #remote mode

5. use

Fn+F8 for saving the selected text into a file as a note.

Fn+F9 for correctness and optimization of your text selected.

Fn+F10 for translation into Chinese.

Fn+F11 for chat with the selected text.



## Acknowledgements:

- [patrickloeber/ai-typing-assistant](https://github.com/patrickloeber/ai-typing-assistant)
- [abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [Vaibhavs10/llama-assistant](https://github.com/Vaibhavs10/llama-assistant)
