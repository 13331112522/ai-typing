from __future__ import annotations

import io,os,sys,time,signal,wave,atexit
import base64
import asyncio
import threading
from typing import Callable, Awaitable

import numpy as np
import pyaudio
import sounddevice as sd
from pydub import AudioSegment

from openai.resources.beta.realtime.realtime import AsyncRealtimeConnection
from openai import AsyncOpenAI, OpenAI

#from pynput import keyboard
import keyboard
import queue
import io
from pynput import keyboard  # Re-import the keyboard module from pynput

from kokoro_onnx import Kokoro

# Initialize Kokoro
kokoro = Kokoro("kokoro-v0_19.onnx", "voices.json")

CHUNK_LENGTH_S = 0.05  # 100ms
SAMPLE_RATE = 24000
FORMAT = pyaudio.paInt16
CHANNELS = 1

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false


def audio_to_pcm16_base64(audio_bytes: bytes) -> bytes:
    # load the audio file from the byte stream
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    print(f"Loaded audio: {audio.frame_rate=} {audio.channels=} {audio.sample_width=} {audio.frame_width=}")
    # resample to 24kHz mono pcm16
    pcm_audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(2).raw_data
    return pcm_audio


class AudioPlayerAsync:
    def __init__(self):
        self.queue = []
        self.lock = threading.Lock()
        self.stream = sd.OutputStream(
            callback=self.callback,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.int16,
            blocksize=int(CHUNK_LENGTH_S * SAMPLE_RATE),
        )
        self.playing = False
        self._frame_count = 0

    def callback(self, outdata, frames, time, status):  # noqa
        with self.lock:
            data = np.empty(0, dtype=np.int16)

            # get next item from queue if there is still space in the buffer
            while len(data) < frames and len(self.queue) > 0:
                item = self.queue.pop(0)
                frames_needed = frames - len(data)
                data = np.concatenate((data, item[:frames_needed]))
                if len(item) > frames_needed:
                    self.queue.insert(0, item[frames_needed:])

            self._frame_count += len(data)

            # fill the rest of the frames with zeros if there is no more data
            if len(data) < frames:
                data = np.concatenate((data, np.zeros(frames - len(data), dtype=np.int16)))

        outdata[:] = data.reshape(-1, 1)

    def reset_frame_count(self):
        self._frame_count = 0

    def get_frame_count(self):
        return self._frame_count

    def add_data(self, data: bytes):
        with self.lock:
            # bytes is pcm16 single channel audio data, convert to numpy array
            np_data = np.frombuffer(data, dtype=np.int16)
            self.queue.append(np_data)
            if not self.playing:
                self.start()

    def start(self):
        self.playing = True
        self.stream.start()

    def stop(self):
        self.playing = False
        self.stream.stop()
        with self.lock:
            self.queue = []

    def terminate(self):
        self.stream.close()


async def send_audio_worker_sounddevice(
    connection: AsyncRealtimeConnection,
    should_send: Callable[[], bool] | None = None,
    start_send: Callable[[], Awaitable[None]] | None = None,
):
    sent_audio = False

    device_info = sd.query_devices()
    print(device_info)

    read_size = int(SAMPLE_RATE * 0.02)

    stream = sd.InputStream(
        channels=CHANNELS,
        samplerate=SAMPLE_RATE,
        dtype="int16",
    )
    stream.start()

    try:
        while True:
            if stream.read_available < read_size:
                await asyncio.sleep(0)
                continue

            data, _ = stream.read(read_size)
            
            if should_send() if should_send else True:
                if not sent_audio and start_send:
                    await start_send()
                print("Sending audio")
                await connection.send(
                    {"type": "input_audio_buffer.append", "audio": base64.b64encode(data).decode("utf-8")}
                )
                sent_audio = True
                #qqprint(connection.input_audio_buffer)
            elif sent_audio:
                print("Done, triggering inference")
                await connection.send({"type": "input_audio_buffer.commit"})
                await connection.send({"type": "response.create", "response": {}})
                sent_audio = False

            await asyncio.sleep(0)

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        stream.close()


def text_to_speech(text):
    """Convert text to speech using macOS say command"""
    try:
        # Use macOS built-in say command
        os.system(f'say "{text}"')
    except Exception as e:
        print(f"TTS Error: {str(e)}")
        print("Fallback to text output:")
        print(text)

def speech_to_text(audio_file):
    """Convert speech to text using Whisper"""
    try:
        import whisper
        import ssl
        
        # Create unverified SSL context
        ssl._create_default_https_context = ssl._create_unverified_context
        
        model = whisper.load_model("base")
        result = model.transcribe(audio_file)
        return result["text"]
    except Exception as e:
        print(f"STT Error: {str(e)}")
        return None

def real_time_voice_chat():
    """Real-time voice chat using Zhipu AI"""
    print("\n=== 语音聊天已开始 (按 Ctrl+C 结束) ===")
    print("注意: 请确保已在系统偏好设置->安全性与隐私->隐私->辅助功能中允许此应用程序")
    
    # Add check for Terminal/iTerm2 accessibility permissions
    if not os.path.exists("/Library/Application Support/com.apple.TCC/TCC.db"):
        print("Please grant accessibility permissions to Terminal/iTerm2:")
        print("1. Go to System Preferences > Security & Privacy > Privacy > Accessibility")
        print("2. Click the lock to make changes")
        print("3. Add Terminal.app or iTerm.app to the list")
        print("4. Restart the terminal and try again")
        return

    try:
        with keyboard.Events() as events:
            # Test if we have input monitoring permissions
            events.get(timeout=0.1)
    except Exception as e:
        print("错误: 需要输入监控权限。请在系统偏好设置中授予权限后重试。")
        return

    import sounddevice as sd
    import scipy.io.wavfile as wav
    import numpy as np
    
    # Audio recording parameters
    sample_rate = 16000  # Zhipu AI prefers 16kHz
    duration = 5  # seconds
    
    try:
        while True:
            # Record audio
            print("\n正在录音... (5秒)")
            recording = sd.rec(int(duration * sample_rate), 
                            samplerate=sample_rate, 
                            channels=1,
                            dtype=np.int16)
            sd.wait()
            
            # Save recording temporarily
            temp_file = "temp_recording.wav"
            wav.write(temp_file, sample_rate, recording)
            
            # Convert speech to text
            text = speech_to_text(temp_file)
            if text:
                print(f"\n你说: {text}")
                
                # Check for stop command
                if any(word in text.lower() for word in ["停止", "结束", "退出", "stop", "quit", "exit"]):
                    print("\n=== 语音聊天已结束 ===")
                    break
                
                # Get AI response
                if args.remote:
                    response = generate_text(text)
                else:
                    response = llm.create_chat_completion(
                        messages=[{"role": "user", "content": text}]
                    )
                
                ai_response = response["choices"][0]["message"]["content"].strip()
                print(f"\nAI: {ai_response}")
                
                # Speak the response
                text_to_speech(ai_response)
            
            # Cleanup
            os.remove(temp_file)
            
    except KeyboardInterrupt:
        print("\n=== 语音聊天已结束 ===")
    finally:
        # Cleanup any remaining temporary files
        if os.path.exists("temp_recording.wav"):
            os.remove("temp_recording.wav")
        if os.path.exists("temp_speech.mp3"):
            os.remove("temp_speech.mp3")


async def realtime_text_chat():
    """Real-time chat using OpenAI's Realtime API"""
    print("\n=== Chat Started (Press Ctrl+C to end) ===")
    
    client = AsyncOpenAI(
        api_key=openai_key,
    )
    
    try:
        async with client.beta.realtime.connect(
            model="gpt-4o-realtime-preview-2024-10-01"  # Changed to use a standard model
        ) as connection:
            await connection.session.update(session={'modalities': ['text']})
            
            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in ['exit', 'quit', 'stop']:
                    break
                
                await connection.conversation.item.create(
                    item={
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_input}],
                    }
                )
                await connection.response.create()
                
                print("AI: ", end="")
                async for event in connection:
                    
                    if event.type == 'response.text.delta':
                        print(event.delta, flush=True, end="")

                    elif event.type == 'response.text.done':
                        print()

                    elif event.type == "response.done":
                        break

    except Exception as e:
        print(f"\nError: {str(e)}")
    except KeyboardInterrupt:
        print("\n=== Chat Ended ===")



async def realtime_audio_chat():
    """Real-time audio chat using OpenAI's Realtime API"""
    print("\n=== Voice Chat Started (Press Ctrl+C to end) ===")
    
    client = AsyncOpenAI(api_key=openai_key)
    audio_player = AudioPlayerAsync()
    last_audio_item_id = None
    running = asyncio.Event()
    running.set()
    is_speaking = False  # Track if voice is detected
    silence_frames = 0
    SILENCE_THRESHOLD = 0  # Number of silent frames before stopping

    device_info = sd.query_devices()
    print(device_info)
    read_size = int(SAMPLE_RATE * 0.02)  # Increased chunk size
    stream = sd.InputStream(
                channels=CHANNELS,
                samplerate=SAMPLE_RATE,
                dtype="int16",
            )
    stream.start()


    def on_press(key):
        try:
            if hasattr(key, 'char') and key.char == 'q':
                print("\nQuitting...")
                running.clear()
                sys.exit(0)  # Exit the entire program
        except AttributeError:
            pass
        except SystemExit:
            raise  # Re-raise SystemExit to properly exit

    try:
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        
        async with client.beta.realtime.connect(
            model="gpt-4o-realtime-preview-2024-10-01"
        ) as connection:
            # Simplified session configuration
            await connection.session.update(
                session={
                    "modalities": ["text", "audio"],
                    "turn_detection": {"type": "server_vad"}
                }
            )
            
            # Initial greeting
            print("\nSending initial greeting...")
            await connection.conversation.item.create(
                item={
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Say hello world"}],
                }
            )
            await connection.response.create()
            
            # Wait for initial response
            async for event in connection:
                if event.type == "response.audio.delta":
                    if event.item_id != last_audio_item_id:
                        audio_player.reset_frame_count()
                        last_audio_item_id = event.item_id
                    bytes_data = base64.b64decode(event.delta)
                    audio_player.add_data(bytes_data)
                elif event.type == "response.text.delta":
                    print(event.delta, end="", flush=True)
                elif event.type == "response.done":
                    print("\nGreeting complete.")
                    break
            

            print("\nStart speaking... (Press 'q' to quit)")
            print("Listening for your voice...")
            
            # Main loop for audio streaming and response handling
            while running.is_set():
                #print(stream.read_available)
                data, _ = stream.read(read_size)
                #if stream.read_available >= read_size:
                

                audio_array = np.frombuffer(data, dtype=np.int16)
                    
                    # Adjusted voice detection threshold
                voice_level = np.abs(audio_array).mean()
                print(f"\rAudio level: {voice_level:.0f}", end="")  # Debug print
                    
                if voice_level > 500:  # Increased threshold
                        silence_frames = 0
                        if not is_speaking:
                            print("\nVoice detected!")
                            is_speaking = True
                        audio_data = base64.b64encode(data.tobytes()).decode("utf-8")
                        await connection.input_audio_buffer.append(audio=audio_data)
                       
                else:
                        if is_speaking:
                            print("\nSilence detected, processing...")
                            silence_frames += 1
                            if silence_frames > SILENCE_THRESHOLD:
                                is_speaking = False
                                await connection.input_audio_buffer.commit()
                                await connection.response.create()
                                async for event in connection:
                                    if event.type == "response.audio.delta":
                                        if event.item_id != last_audio_item_id:
                                            audio_player.reset_frame_count()
                                            last_audio_item_id = event.item_id
                                            print("\nReceiving audio response...")
                                        bytes_data = base64.b64decode(event.delta)
                                        audio_player.add_data(bytes_data)
                                    elif event.type == "response.text.delta":
                                        print(event.delta, end="", flush=True)
                                    elif event.type == "response.done":
                                        print("\nResponse complete.")
                                        break
                
                
                await asyncio.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n=== Voice Chat Ended ===")
    finally:
        print("\nCleaning up...")
        listener.stop()
        if 'stream' in locals():
            stream.stop()
            stream.close()
        audio_player.terminate()
        print("=== Voice Chat Ended ===")

class RealtimeAudioChat:
    def __init__(self, api_key):
        self.api_key = api_key
        self.running = asyncio.Event()
        self.should_record = asyncio.Event()
        self.audio_player = None
        self.thread = None
        self._loop = None
        
    def start(self):
        """Start the audio chat in a separate thread"""
        self.running.set()
        self.thread = threading.Thread(target=self._run_async_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """Stop the audio chat"""
        if self._loop:
            self._loop.call_soon_threadsafe(self.running.clear)
        if self.thread:
            self.thread.join()
            
    def start_recording(self):
        """Start recording (called when K is pressed)"""
        if self._loop:
            self._loop.call_soon_threadsafe(self.should_record.set)
            
    def stop_recording(self):
        """Stop recording (called when K is released)"""
        if self._loop:
            self._loop.call_soon_threadsafe(self.should_record.clear)
            
    async def _run_chat(self):
        """Main chat logic"""
        try:
            client = AsyncOpenAI(api_key=self.api_key)
            self.audio_player = AudioPlayerAsync()
            last_audio_item_id = None
            sent_audio = False
            
            while self.running.is_set():  # Main connection loop
                try:
                    async with client.beta.realtime.connect(
                        model="gpt-4o-realtime-preview-2024-10-01"
                    ) as connection:
                        print("\nConnecting to OpenAI...")
                        await connection.session.update(
                            session={
                                "modalities": ["text", "audio"],
                                "turn_detection": {"type": "server_vad"}  # Use server VAD like RealtimeApp
                            }
                        )
                        
                        print("\nVoice chat started (Press K to talk)")
                        
                        read_size = int(SAMPLE_RATE * 0.02)
                        stream = sd.InputStream(
                            channels=CHANNELS,
                            samplerate=SAMPLE_RATE,
                            dtype="int16",
                        )
                        stream.start()
                        print("\nStream started")
                        
                        while self.running.is_set():
                            if stream.read_available < read_size:
                                await asyncio.sleep(0)
                                continue

                            data, _ = stream.read(read_size)
                            
                            if self.should_record.is_set():
                                if not sent_audio:
                                    print("\nStarting new recording...")
                                    sent_audio = True
                                print("\rRecording...", end="", flush=True)
                                
                                # Send audio data
                                audio_data = base64.b64encode(data).decode("utf-8")
                                await connection.input_audio_buffer.append(
                                    audio=audio_data
                                )
                                print("Audio data sent.")  # Debug statement
                            
                            elif sent_audio:  # Key released and we have recorded audio
                                print("\nProcessing audio...")
                                try:
                                    # Commit the audio buffer and request response
                                    await connection.input_audio_buffer.commit()
                                    await connection.response.create()
                                    sent_audio = False
                                    
                                    print("Waiting for response...")
                                    async for event in connection:
                                        print(f"Received event: {event.type}")  # Debug print
                                        
                                        if event.type == "response.audio.delta":
                                            if event.item_id != last_audio_item_id:
                                                self.audio_player.reset_frame_count()
                                                last_audio_item_id = event.item_id
                                                print("\nPlaying audio response...")
                                            bytes_data = base64.b64decode(event.delta)
                                            self.audio_player.add_data(bytes_data)
                                        
                                        elif event.type == "response.text.delta":
                                            print(event.delta, end="", flush=True)
                                        
                                        elif event.type == "response.done":
                                            print("\nResponse complete.")
                                            break
                                        
                                        elif event.type == "error":
                                            print(f"\nError: {event}")
                                            break
                                    
                                except Exception as e:
                                    print(f"\nError during response: {e}")
                                    break  # Break inner loop to reconnect
                            
                            await asyncio.sleep(0.01)
                        
                        #event_task.cancel()
                        if 'stream' in locals():
                            stream.stop()
                            stream.close()
                
                except Exception as e:
                    print(f"\nConnection error: {e}")
                    print("Reconnecting in 2 seconds...")
                    await asyncio.sleep(2)
                    continue  # Retry connection
                
        except Exception as e:
            print(f"\nFatal error in voice chat: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if 'stream' in locals():
                stream.stop()
                stream.close()
            if self.audio_player:
                self.audio_player.terminate()
            print("\nVoice chat ended")
    
    def _run_async_loop(self):
        """Run the async event loop in the thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_chat())


class WhisperRecorder:
    def __init__(self, api_key: str, sample_rate: int = 16000):
        self.client = OpenAI(api_key=api_key)
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self.recorded_frames = []
        self.stream = None
        self.listener = None
        self.should_quit = False
        atexit.register(self.cleanup)
        
        # Test microphone access
        try:
            test_stream = sd.InputStream(
                channels=1,
                samplerate=sample_rate,
                dtype=np.int16
            )
            test_stream.start()
            test_stream.stop()
            test_stream.close()
        except Exception as e:
            print("\nError: Cannot access microphone. Please check your system settings:")
            print("1. System Preferences > Security & Privacy > Privacy > Microphone")
            print("2. Ensure Terminal/Python has microphone access")
            print("3. Restart Terminal after granting permissions")
            sys.exit(1)

    def cleanup(self):
        """Cleanup resources"""
        if self.stream:
            try:
                self.recording = False
                time.sleep(0.1)  # Give time for callback to complete
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None

    def start_recording(self):
        """Start recording audio"""
        try:
            if self.stream:
                self.cleanup()
                
            self.recording = True
            self.recorded_frames = []
            
            print("Starting recording...")  # Debug statement
            
            def callback(indata, frames, time, status):
                if status:
                    print('Error:', status)
                if self.recording:
                    self.recorded_frames.extend(indata.copy())
            
            self.stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                dtype=np.int16,
                callback=callback,
                blocksize=8192
            )
            self.stream.start()
            sys.stdout.write('\rRecording...')
            sys.stdout.flush()
        except Exception as e:
            print(f"\nError starting recording: {e}")
            self.recording = False
            self.cleanup()

    def stop_recording(self):
        """Stop recording and save audio"""
        if self.recording:
            print("Stopping recording...")  # Debug statement
            self.recording = False
            time.sleep(0.1)  # Give time for callback to complete
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            return np.array(self.recorded_frames)
        return None

    def save_wav(self, audio_data, filename="temp_audio.wav"):
        """Save audio data to WAV file"""
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit audio
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        return filename

    def whisper_call(self, audio_data):
        """Convert audio to text using Whisper API"""
        try:
            # Save audio to temporary WAV file
            temp_file = self.save_wav(audio_data)
            
            # Call Whisper API
            with open(temp_file, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            
            # Clean up temporary file
            os.remove(temp_file)
            
            return transcript
        except Exception as e:
            print(f"\nError in Whisper API call: {e}")
            return None

    

    def start_listening(self):
        """Start listening for keyboard events"""
        self.transcript = []
        
        # Start recording immediately
        self.start_recording()
        print("Recording... (Press 'q' to stop)")

        def on_press(key):
            """Handle key press events"""
            try:
                if key.char == 'q':  # Check if 'q' is pressed
                    print("\nProcessing...")
                    audio_data = self.stop_recording()
                    if audio_data is not None:
                        transcript = self.whisper_call(audio_data)
                        if transcript:
                            print("\nTranscription:", transcript)
                            self.transcript.append(transcript)
                        else:
                            print("\nTranscription failed")
                    print("\nReady to record (Press 'q' to quit)")
                    return False  # Stop the listener
            except AttributeError:
                
                pass

        # Start the listener
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()  # Wait for the listener to finish

        return self.transcript

def play_audio_with_kokoro(text):
    """Convert text to audio using Kokoro and play it."""
    #print(f"Playing audio with Kokoro: {text}")
    samples, sample_rate = kokoro.create(text, voice="af_sarah", speed=1.0, lang="en-us")
    print("Playing audio...")
    sd.play(samples, sample_rate)
    #sd.wait()
    print("Audio played")
    return
