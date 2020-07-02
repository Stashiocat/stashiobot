from twitchio.ext import commands
from auth import Auth
from channel_rewards import ChannelRewards
from pubsub import PubSubHandler
from pubsub import PubSubReturn
from utils.language import MessageTranslator

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
                
bot = Bot()
bot.run()
