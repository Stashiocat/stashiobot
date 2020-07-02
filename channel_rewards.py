import utils.tts as tts
from utils.images import ImageHandler
import re
import json

class ChannelRewards():
    def __init__(self):
        self.__obs_pic_location = 'stashiobot_pic'
        self.__stashio_pic_folder = 'stashio_pictures'
        self.__image_handler = ImageHandler(self.__obs_pic_location, self.__stashio_pic_folder)
    
        self.__voice = tts.TTS()
        self.__channel_rewards = {
            '79d9ed5c-6f65-4b81-8c27-71a9f3d7b181':
            {
                'Name': 'TTS',
                'Callback': self.__callback_TTS
            },
            'e86c82b1-0d47-4f18-aa00-d6f9c764e4d4':
            {
                'Name': 'Change Stashio pic',
                'Callback': self.__callback_Change_Pic
            }
        }
    
    ###########################################################################
    # Callbacks
    ###########################################################################
    def __callback_TTS(self, user, message):
        voice_id, message = self.__parse_voice_id_and_message(message)
        print(f'TTS from {user}: {message}')
        
        tts_message = '{user} says... {message}'.format(user=user, message=message)
        self.__speak_tts_blocking(voice_id, tts_message)
        
    def __callback_Change_Pic(self, user, message):
        print(f'Stashio pic changed by {user}')
        self.__image_handler.next_pic()
    
    ###########################################################################
    # Public facing methods
    ###########################################################################            
    def handle_pubsub_reward(self, reward_id, user, message):
        if reward_id in self.__channel_rewards:
            reward = self.__channel_rewards[reward_id]
            reward['Callback'](user, message)
        else:
            print(f"Channel reward '{reward_id}' not found.")
            
    ###########################################################################
    # Private helper methods
    ###########################################################################
    def __parse_voice_id_and_message(self, message):
        r = re.findall(r'\<(\d)\>(.*)', message)
        voice_id = -1
        if r:
            voice_id = int(r[0][0])
            message = r[0][1]
            
        return voice_id, message
        
    def __speak_tts_blocking(self, voice_id, tts_message):
        self.__voice.speak_tts_blocking(voice_id, tts_message)