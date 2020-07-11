import signal
import asyncio, concurrent.futures
from twitchio.ext import commands
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
            irc_token=self.auth.get_irc_token(),
            client_id=self.auth.get_client_id(),
            nick='Stashiobot',
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
                    samus_dead         = None #self.samus_dead
                )
        self.sm_manager = SuperMetroidRunManager(sm_callbacks)
        
        self.__executor = concurrent.futures.ThreadPoolExecutor()

    def run_started(self):
        print('Run started')
        
    def run_reset(self):
        print('Run reset')
        
    def enter_phantoon(self):
        channel = self.get_channel('stashiocat')
        self.__executor.submit(asyncio.run, channel.send('!phanclose'))
        
    def enter_moat(self):
        channel = self.get_channel('stashiocat')
        self.__executor.submit(asyncio.run, channel.send('!phanopen'))
    
    def phantoon_fight_end(self, patterns):
        channel = self.get_channel('stashiocat')
        self.__executor.submit(asyncio.run, channel.send(f"!phanend {' '.join(patterns)}"))
    
    async def event_ready(self):
        print('Connected!')
        await self.pubsub.subscribe_for_channel_rewards()
    
    async def event_raw_pubsub(self, data):
        result = await self.pubsub.handle_rewards(data, self.rewards)
        if result == PubSubReturn.ExpiredAccessToken:
            await self.pubsub.subscribe_for_channel_rewards()
    
    async def event_message(self, message):
        if message.author.name.lower() != self.nick.lower():
            prefix = await self.get_prefix(message)
            if not prefix:
                src, dst, msg = self.translator.chat_auto_translate(message)
                if src and dst and msg:
                    await message.channel.send(f'{src} => {dst}: {msg}')
                    return
                 
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
