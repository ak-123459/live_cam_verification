import pyttsx3
import threading

def speak_async(text, voice=None):
    """Speak text asynchronously using pyttsx3"""
    def _speak():
        engine = pyttsx3.init()
        if voice:
            engine.setProperty('voice', voice)  # Set Hindi or other voice
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=_speak, daemon=True).start()
