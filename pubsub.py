import json
import requests
import random
from enum import Enum
from utils.jsonparse import JsonParse

class PubSubReturn(Enum):
    Success = 0
    ExpiredAccessToken = 1
    BadAuth = 2
    UnknownError = 3

class PubSubHandler():
    def __init__(self, twitch_bot, auth, channels):
        self.__twitch_bot = twitch_bot
        self.__auth = auth
        self.__channels = channels
        
    ###########################################################################
    # Public facing methods
    ###########################################################################    
    async def subscribe_for_channel_rewards(self):
        topics = self.__get_channel_reward_topics(self.__channels)
        await self.__twitch_bot.pubsub_subscribe(self.__auth.get_access_token(), *topics)
        
    async def handle_rewards(self, data, rewards):
        if not 'type' in data:
            return PubSubReturn.UnknownError
            
        if data['type'] == "RESPONSE":
            if data['error'] == '':
                print("PubSub enabled.")
            elif data['error'] == 'ERR_BADAUTH':
                if not self.__auth.validate_access_token():
                    self.__auth.refresh_access_token()
                    print('Your access token has expired. The token has been refreshed.')
                    return PubSubReturn.ExpiredAccessToken
                else:
                    print('Received ERR_BADAUTH but access token has not expired. Are you subscribing to the wrong channel?')
                    return PubSubReturn.BadAuth
            else:
                print('Error:', data['error'])
                return PubSubReturn.UnknownError
                
        elif data['type'] == "MESSAGE":
            parse = JsonParse(json.loads(data['data']['message']))
            if parse.get('type') == "reward-redeemed":
                user = parse.get('data/redemption/user/login')
                reward = parse.get('data/redemption/reward')
                message = parse.get('data/redemption/user_input')
                reward_id = parse.get('data/redemption/reward/id')
                
                rewards.handle_pubsub_reward(reward_id, user, message)
                
        return PubSubReturn.Success
            
    ###########################################################################
    # Private helper methods
    ###########################################################################
    def __debug_get_access_token(self, oauth_code):
        url = f'https://id.twitch.tv/oauth2/token?client_id={self.__auth.get_client_id()}&client_secret={self.__auth.get_client_secret()}&code={oauth_code}&grant_type=authorization_code&redirect_uri=http://localhost'
        r = requests.post(url)
        print(r.content)
        
    def __get_channel_ids(self, channels):
        headers = {
            'Client-ID': self.__auth.get_client_id(),
            'Authorization': f'Bearer {self.__auth.get_access_token()}'
        }
        r = requests.get(f'https://api.twitch.tv/helix/users?login={"&topic=".join(channels)}', headers=headers)
        j = json.loads(r.content)
        return [j['data'][i]['id'] for i in range(len(channels))]
        
    def __get_channel_reward_topics(self, channels):
        channel_ids = self.__get_channel_ids(channels)
        return [f'channel-points-channel-v1.{channel}' for channel in channel_ids]
        
    def __generate_nonce(length=8):
        return ''.join([str(random.randint(0, 9)) for i in range(length)])