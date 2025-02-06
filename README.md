# LLaMA Assistant for Mac with remote mode

A simple assistant for Mac that both support `llama-cpp-python` to assist you locally with Qwen0.5-Instruct and remotely with Zhipu GLM-4-airX (easy to extend to other LLMs according to your needs).

## Latest Updates:

1. **Voice Interaction Features**:
   - **Fn+F7**: Real-time voice chat using OpenAI's API
     - Press 'k' to start recording your voice
     - Release 'k' to get AI's response
     - Press 'q' to exit chat session
   - **Fn+F6**: Voice transcription using Whisper
     - Press F6 to start recording
     - Press 'q' to stop and get transcription
     - Automatically saves transcription to notes
   - **Fn+F5**: Text-to-Speech with Kokoro
     - Select text and press F5 to hear it spoken
     - Supports multiple voices and languages

2. **Text Interaction Features**:
   - **Fn+F11**: Chat with selected text (questions, translation, optimization)
   - **Fn+F10**: Translate selected text to Chinese
   - **Fn+F9**: Fix and optimize selected text
   - **Fn+F8**: Save selected text as notes (Obsidian compatible)

## Why?

Because I wanted a more pythonic solution and wanted to build something w/ llama-cpp-python.

Because sometimes purely local mode with llama-cpp-python is not enough, I wanted to use remote model to get better results.

- Provides a more pythonic solution built with llama-cpp-python
- Combines local processing with powerful remote APIs for better results
- Offers comprehensive voice interaction capabilities

## Setup

Create a virtual environment and follow the steps below.

1. Install llama-cpp-python

`CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python`

Note: If you are on CUDA/ CPU, you can remove the `CMAKE_ARGS="-DGGML_METAL=on"` part and  replace with appropriate cmake args [here](https://llama-cpp-python.readthedocs.io/en/latest/#supported-backends).

2. Install necessary libs

`pip install pynput pyperclip openai sounddevice numpy pyaudio pydub kokoro_onnx`

3. Download the model and put it in the same dir as the main.py

  - qwen2-0_5b-instruct-q8_0.gguf (for local LLM)
  - kokoro-v0_19.onnx (for text-to-speech)
  - voices.json (voice configurations)

4. Set Up API Keys
- OpenAI API key for voice features
- Zhipu API key for remote text processing


5. Run 

`python main.py #local mode`

`python main.py -R #remote mode`


6. usage

### Voice Commands
- **F7**: Real-time voice chat
- **F6**: Voice transcription
- **F5**: Text-to-speech

### Text Commands
- **F11**: Interactive chat with selected text
- **F10**: Chinese translation
- **F9**: Text optimization
- **F8**: Save to notes

### System
- **F4**: Exit program

## Requirements

- macOS (for full feature support)
- Python 3.8+
- Microphone access
- Terminal/iTerm2 accessibility permissions



## Acknowledgements:

- [patrickloeber/ai-typing-assistant](https://github.com/patrickloeber/ai-typing-assistant)
- [abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [Vaibhavs10/llama-assistant](https://github.com/Vaibhavs10/llama-assistant)
