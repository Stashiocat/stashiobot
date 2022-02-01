import signal
import random
import asyncio, concurrent.futures
import requests
from concurrent.futures import ThreadPoolExecutor
from twitchio.ext import commands
import twitchio
from auth import Auth
from channel_rewards import ChannelRewards
from pubsub import PubSubHandler, PubSubReturn
from supermetroidmanager import SuperMetroidRunManager, SuperMetroidCallbacks
from utils.language import MessageTranslator
from utils.supermetroid import SuperMetroid, Rooms

class Bot(commands.Bot):
    def __init__(self):
        self.initial_channels = [
            'stashiocat'
        ]
        
        self.auth = Auth('auth.json')
    
        super().__init__(
            token=self.auth.get_irc_token(),
            nick=self.auth.get_user(),
            prefix='!',
            initial_channels=self.initial_channels
        )

        self.rewards = ChannelRewards()
        self.pubsub = PubSubHandler(self, self.auth, self.initial_channels)
        self.translator = MessageTranslator()
        
        sm_callbacks = SuperMetroidCallbacks(
                    run_started        = self.run_started,
                    run_reset          = self.run_reset,
                    enter_phantoon     = self.enter_phantoon,
                    enter_moat         = self.enter_moat,
                    phantoon_fight_end = self.phantoon_fight_end,
                    samus_dead         = None,
                    ceres_start        = self.ceres_start,
                    ceres_end          = self.ceres_end,
                    ceres_timer        = self.ceres_timer,
                )
        self.sm_manager = SuperMetroidRunManager(sm_callbacks)
        self.sm_games = True
        self.is_phan_open = False
        self.is_ceres_open = False
        self.is_ceres_timer_ready = False
        self.pool_executor = concurrent.futures.ThreadPoolExecutor()
        
    def enable_threads(self, loop):
        loop.create_task(input_thread(self))
        self.sm_manager.enable_threads(loop)

    def funtoon_custom_event(self, event_name, event_data=None):
        if self.sm_games:
            headers = {
                'Authorization': self.auth.get_funtoon_token(),
                'Content-Type': 'Application/json'
            }
            content_data = {
                'channel': self.auth.get_user(),
                'event': event_name,
                'data': event_data
            }
            r = requests.post('https://funtoon.party/api/events/custom', headers=headers, json=content_data)

    def run_started(self):
        print('Run started')
            
    def run_reset(self):
        print('Run reset')
        
    def enter_phantoon(self):
        if self.is_phan_open:
            self.is_phan_open = False
            self.funtoon_custom_event('phanclose')
        
    def enter_moat(self):
        if not self.is_phan_open:
            self.is_phan_open = True
            self.funtoon_custom_event('phanopen')
    
    def phantoon_fight_end(self, patterns):
        self.funtoon_custom_event('phanend', ' '.join(patterns))
    
    def ceres_start(self):
        if not self.is_ceres_open:
            self.is_ceres_open = True
            self.funtoon_custom_event('ceresopen')
        
    def ceres_end(self):
        if self.is_ceres_open:
            self.is_ceres_open = False
            self.is_ceres_timer_ready = True
            self.funtoon_custom_event('ceresclose')
            
    def ceres_timer(self, time):
        if self.is_ceres_timer_ready:
            self.is_ceres_timer_ready = False
            self.funtoon_custom_event('ceresend', hex(time)[2::])
            
    async def event_ready(self):
        print('Connected!')
        await self.pubsub.subscribe_for_channel_rewards(self.auth.get_access_token(), self.initial_channels[0])
        
    async def event_raw_pubsub(self, data):
        result = await self.pubsub.handle_rewards(data, self.rewards)

    async def event_pubsub_channel_points(self, msg):
        self.rewards.handle_pubsub_reward(msg.reward.id, msg.user.name, msg.input)
    
    async def event_token_expired(self):
        return self.__auth.refresh_access_token()
    
    async def event_message(self, message):
        if message.author and message.author.name.lower() != self.nick.lower():
            prefix = await self.get_prefix(message)
            if not prefix:
                src, dst, msg = self.translator.chat_auto_translate(message)
                if src and dst and msg and (msg != message.content):
                    await message.channel.send(f'{src} => {dst}: {msg}')
                    return
                 
            await self.handle_commands(message)

    async def event_raw_data(self, data):
        #print(data)
        pass
        
    async def event_command_error(self, ctx, error):
        pass
        
    @commands.command(name='nou')
    async def no_u(self, ctx):
        await ctx.send('NO U')
    
    @commands.command(name='deerforce')
    async def deerforce(self, ctx):
        await ctx.send(' '.join([chr(ord(c) & ~(random.randint(0,1)*32)) for c in "deerforce"]))
            
async def start_bot(bot):
    bot.run()
            
async def ainput(prompt: str = ''):
    with ThreadPoolExecutor(1, 'ainput') as executor:
        return (await asyncio.get_event_loop().run_in_executor(executor, input, prompt)).rstrip()

async def input_thread(bot):
    while True:
        inp = await ainput("(input) >> ")
        if len(inp) > 0 and inp[0] == '/':
            inp = inp[1::]
            if inp.lower() == "smtoggle":
                bot.sm_games = not bot.sm_games
                print(f'Super Metroid games are now {"on" if bot.sm_games else "off"}')
    
if __name__ == '__main__':
    # make Ctrl-C actually kill the process
    bot = Bot()
    loop = asyncio.get_event_loop()
    loop.create_task(input_thread(bot))
    bot.run()
    signal.signal(signal.SIGINT, signal.SIG_DFL)