from asyncio import iscoroutine

from cogs.utils.custom_cog import Cog
from cogs.utils.custom_context import NoOutputContext, CustomContext
from cogs.utils.custom_bot import CustomBot
from cogs.utils.family_tree.family_tree_member import FamilyTreeMember


class RedisHandler(Cog):

    def __init__(self, bot:CustomBot):
        self.bot = bot 
        super().__init__(__class__.__name__)
        task = bot.loop.create_task
        self.handlers = [
            task(self.channel_handler('TreeMemberUpdate', lambda data: FamilyTreeMember(**data))),
            task(self.channel_handler('RunGlobalCommand', self.run_global_command))
        ]
        self.channels = []  # Populated automatically


    def cog_unload(self):
        for handler in self.handlers:
            handler.cancel()
        for channel in self.channels.copy():
            self.bot.run_until_complete(self.bot.redis.pool.unsubscribe(channel))
            self.channels.remove(channel)


    async def channel_handler(self, channel_name:str, function:callable):
        '''
        General handler for creating a channel, waiting for an input, and then 
        plugging the data into a function
        '''

        # Subscribe to the given channel
        self.channels.append(channel_name)
        async with self.bot.redis() as re:
            self.log_handler.debug(f"Subscribing to Redis channel {channel_name}")
            channel_list = await re.conn.subscribe(channel_name)

        # Get the channel from the list, loop it forever
        self.channel = channel = channel_list[0]
        self.log_handler.debug(f"Looping to wait for messages to channel {channel_name}")
        while (await channel.wait_message()):

            # Get and log the data
            self.log_handler.debug(f"Received Redis message to {channel_name}")
            data = await channel.get_json()
            self.log_handler.debug(f"Redis {channel_name}: {data!s}")
            
            # Run the callable
            if iscoroutine(function):
                return await function(data)
            return function(data)

        
    async def run_global_command(self, data:dict):
        '''Runs a given command globally, across all shards'''

        # Get guild
        guild_id = data['guild_id']
        guild = self.bot.get_guild(guild_id)
        if not guild:
            guild = await self.bot.fetch_guild(guild_id)

        # Get channel
        channel = guild.get_channel(data['channel_id'])

        # Get message
        message = await message.fetch_message(data['message_id'])

        # Change message content
        message.content = data['command']

        # Invoke command
        if guild.shard_id in self.bot.shard_ids:
            ctx = self.bot.get_context(message, cls=CustomContext)
        else:
            ctx = self.bot.get_context(message, cls=NoOutputContext)
        await self.bot.invoke(ctx)


def setup(bot:CustomBot):
    x = RedisHandler(bot)
    bot.add_cog(x)
