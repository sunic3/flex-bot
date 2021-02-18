import discord
from discord.ext import commands
from discord.ext.commands import has_permissions
from cogs.bot import channel_check, ChannelException

from bottools import exp, postix, mcm, channels_perms
from cfg import me, version

import asyncio


class Extra(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.bugs = []

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.client.user}#{self.client.user.id} is active!')
        with open('update.txt', 'r', encoding='utf-8') as f:
            update = f.readlines()
        if len(update) > 0:
            for guild in self.client.guilds:
                embed = discord.Embed(
                    colour=discord.Colour.green(),
                    title='Важное обновление',
                    description=f'Привет, `{guild.name}` :heart_exclamation: Мне приятно, что мы с тобой ещё дружим и '
                                f'весело проводим время. Настало время порадовать тебя плюшками новой '
                                f'версии `{version}`:\n\n' + '\n'.join(f'- {e[:-1]};' for e in update)
                )
                embed.set_footer(text='это сообщение автоматически исчезнет через 24 часа.')
                await discord.utils.get(guild.text_channels, id=channels_perms(guild)).send(embed=embed,
                                                                                            delete_after=86400)

    @commands.command(name='clear', aliases=['c'])
    @has_permissions(manage_messages=True)
    async def clear_(self, ctx, n='all'):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        if n != 'all':
            try:
                await ctx.channel.purge(limit=int(n)+1)
            except ValueError:
                await ctx.send(f'Не удалось распознать число `{n}`')
        else:
            await ctx.channel.purge(limit=100)

    @clear_.error
    async def clear_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.message.delete()
            await ctx.send('У тебя не достаточно прав, чтобы удалять сообщения :stop_sign:', delete_after=10)
        else:
            await exp(ctx)

    @commands.command(name='bug')
    async def bug_(self, ctx, *, msg: str):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        if ctx.message.author.id in self.bugs:
            await ctx.send(f'Прости `{ctx.message.author.name}` но отправка сообщений такого рода не '
                           f'должна быть чаще 1 раза в минуту :clock1:', delete_after=10)
        else:
            self.bugs.append(ctx.message.author.id)
            user = await self.client.fetch_user(me)
            user.send(f'сервер: {ctx.guild.name}\nавтор: {ctx.message.author.mention}\nтекст: {msg}')
            await ctx.send(f'`{ctx.message.author.name}` спасибо за помощь в разработке :diving_mask: ',
                           delete_after=20)
            await mcm(ctx)
            await asyncio.sleep(60)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            self.bugs.remove(ctx.message.author.id)

    @bug_.error
    async def bug_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.message.delete()
            await ctx.send(f'Ты забыл{postix(ctx)} описать проблему :pen_ballpoint:', delete_after=20)
        else:
            await exp(ctx)

    @commands.command(name='git')
    async def github_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        await ctx.send(':house: мой домик: https://github.com/gitSunic/flex-bot', delete_after=40)
        await mcm(ctx)

    @commands.command(name='extra_help', aliases=['d.h'])
    async def extra_help_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        await ctx.message.delete()
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(r=30, g=144, b=255),
            description=f':broom:`.clear` - удалю последние *n* сообщений на канале, но не более 100 за раз!\n'
                        f':crab:`.bug` - если ты найдешь какие-то значимы ошибки в моей работе, обязательно '
                        f'отправь их мне при помощи этой команды.\n'
                        f':mermaid:`.git` - **разденусь перед тобой полностью** (всмысле пришлю ссылку на свой '
                        f'открытый код, а ты о чём подумал{postix(ctx)}? хе-хе)'
        )
        embed.set_author(name='Дополнительные команды',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)


def setup(client):
    client.add_cog(Extra(client))
