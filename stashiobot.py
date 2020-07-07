import signal
import threading
import time
from twitchio.ext import commands
from auth import Auth
from channel_rewards import ChannelRewards
from pubsub import PubSubHandler, PubSubReturn
from utils.language import MessageTranslator
from utils.supermetroid import SuperMetroid

class Bot(commands.Bot):
    
    def __init__(self):
        self.initial_channels = [
            'stashiocat'
        ]
        
        self.auth = Auth('auth.json')
    
        super().__init__(
            irc_token=self.auth.get_irc_token(),
            client_id=self.auth.get_client_id(),
            nick='Stashiobot',
            prefix='!',
            initial_channels=self.initial_channels
        )

        self.rewards = ChannelRewards()
        self.pubsub = PubSubHandler(self, self.auth, self.initial_channels)
        self.translator = MessageTranslator()
        self.sm = SuperMetroid()
        self.sm.start_game_info_update(0.2)
        
        self.sm.subscribe_for_run_start(self.run_started)
        self.sm.subscribe_for_enter_phantoon(self.enter_phantoon)
        self.sm.subscribe_for_enter_moat(self.enter_moat)
        
    def run_started(self):
        print('Good luck, have fun!')
        
    def enter_phantoon(self):
        print('Phantoon started!')
        
    def enter_moat(self):
        print('Entered moat!')
        
    async def event_ready(self):
        print('Connected!')
        await self.pubsub.subscribe_for_channel_rewards()
    
    async def event_raw_pubsub(self, data):
        result = await self.pubsub.handle_rewards(data, self.rewards)
        if result == PubSubReturn.EXPIRED_ACCESS_TOKEN:
            await self.pubsub.subscribe_for_channel_rewards()
    
    async def event_message(self, message):
        if message.author.name.lower() != self.nick.lower():
            prefix = await self.get_prefix(message)
            if not prefix:
                await self.translator.chat_auto_translate(message)
            else:
                await self.handle_commands(message)

    async def event_raw_data(self, data):
        #print(data)
        pass
        
    async def event_command_error(self, ctx, error):
        pass
        
    @commands.command(name='nou')
    async def my_command(self, ctx):
        await ctx.send('NO U')

# make Ctrl-C actually kill the process
signal.signal(signal.SIGINT, signal.SIG_DFL)

bot = Bot()
bot.run()
