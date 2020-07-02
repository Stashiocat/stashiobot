import pyttsx3
import random

class TTS():
    def __init__(self, volume=0.55):
        self.__tts_engine = pyttsx3.init()
        self.__tts_voices = self.__tts_engine.getProperty('voices')
        
        self.__tts_engine.setProperty('volume', volume)
        
        self.tts_voice_names = [
            'Microsoft David Desktop - English (United States)',
            'Microsoft Hazel Desktop - English (Great Britain)',
            'Microsoft Hedda Desktop - German',
            'Microsoft Zira Desktop - English (United States)',
            'Microsoft Helena Desktop - Spanish (Spain)',
            'Microsoft Sabina Desktop - Spanish (Mexico)',
            'Microsoft Hortense Desktop - French',
            'Microsoft Haruka Desktop - Japanese',
            'Microsoft Heami Desktop - Korean',
            'Microsoft Irina Desktop - Russian'
        ]
        
    ###########################################################################
    # Public facing methods
    ###########################################################################
    def find_voice(self, name_to_find):
        for i in range(len(self.__tts_voices)):
            if self.__tts_voices[i].name == name_to_find:
                return self.__tts_voices[i].id
        return self.__tts_voices[random.randrange(0, len(self.__tts_voices))].id
        
    def speak_tts_blocking(self, voice_id, msg):
        if 0 > voice_id or voice_id >= len(self.tts_voice_names):
            voice_id = random.randrange(0, len(self.__tts_voices))
            
        voice_id = self.find_voice(self.tts_voice_names[voice_id])
        
        self.__tts_engine.setProperty('voice', voice_id)
        self.__tts_engine.say(msg)
        self.__tts_engine.runAndWait()