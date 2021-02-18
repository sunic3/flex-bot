import discord
from discord.ext import commands

from cfg import imgbb_token
from cogs.bot import channel_check, ChannelException
from bottools import postix

import requests
import random


class Enter(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command(aliases=['e.r'])
    async def random(self, ctx, q):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            a, b = map(int, q.split('-'))
            await ctx.send(f'{ctx.message.author.mention} твоё случайное '
                           f'число от {a} до {b}: **{random.randint(a, b)}**', delete_after=40)
        except ValueError:
            await ctx.send(f'Ты неправильно ввел{postix(ctx)} данные :sweat:', delete_after=10)
        except commands.errors.MissingRequiredArgument:
            await ctx.send('Укажи границы :sweat:', delete_after=10)

    @commands.command(name='upload', aliases=['e.url', 'e.u'])
    async def image_upload_(self, ctx):
        for attachment_url in ctx.message.attachments:
            file_request = requests.get(attachment_url.url)
            res = requests.post(url='https://api.imgbb.com/1/upload',
                                params={'key': imgbb_token, 'name': attachment_url.filename},
                                files={'image': file_request.content}).json()
            await ctx.send(f'Теперь это изображение доступно по ссылке: {res["data"]["url"]}')
            return
        raise commands.errors.BadArgument

    @image_upload_.error
    async def image_upload_error(self, ctx, error):
        if isinstance(error, commands.errors.BadArgument):
            await ctx.message.delete()
            await ctx.send(f'ты забыл{postix(ctx)} прикрепить файл', delete_after=40)
        else:
            await ctx.message.delete()
            print(error)
            await ctx.send('Неизвестная ошибка :eyes:', delete_after=40)

    @commands.command(name='enter_help', aliases=['e.h'])
    async def enter_help_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(r=30, g=144, b=255),
            description=':game_die:`.e.r`,`.random` - передай вместе с командой строку в виде '
                        '`a-b` и я выберу случайное число от *a* до *b* включительно. '
                        '*a и b - целые числа*\n'
                        ':arrow_up:`.e.u`,`.upload` - отправь с командой картинку и получи короткую ссылку на нее'

        )
        embed.set_author(name='Развлекательные команды',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)


def setup(client):
    client.add_cog(Enter(client))
