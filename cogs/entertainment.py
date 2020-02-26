import discord
from discord.ext import commands
from discord.ext.commands import has_permissions

from cfg import imgbb_token
from cogs.bot import channel_check, ChannelException
from bottools import postix

from PIL import Image, ImageFont, ImageDraw
import io
import re
import os
import requests
import random
import asyncio


# words = re.findall(r'<td class="text">(\w+)</td>', open('cogs/words.txt', 'r', encoding='utf-8').read())
# words = open('cogs/words.txt', 'r', encoding='utf-8').read().split(' ')
#
#
# class Word:
#     def __init__(self, id, text):
#         self.id = id
#         self.text = text
#         self.mode = 'b' if id == 0 else 'w' if id in range(1, 8) else 'r' if id in range(8, 16) else 'i'
#         self.fz = 40
#
#     def __str__(self):
#         return f'{str(self.id)}.{self.text}:{self.mode}'
#
#
# def bg_create(codewords):
#     bg = Image.new('RGB', (1512, 512), (246, 79, 23))
#     for i in range(25):
#         word = codewords[i].text
#         im = Image.new('RGB', (300, 100), (255, 250, 205))
#         draw = ImageDraw.Draw(im)
#         for fz in range(40, 10, -2):
#             w, h = draw.textsize(text=word, font=ImageFont.truetype('arial.ttf', size=fz))
#             if w < 260:
#                 break
#         x, y = (300 - w) / 2, (100 - h) / 2
#         codewords[i].fz = fz
#         draw.text(xy=(x, y), text=word, fill=(0, 0, 0), font=ImageFont.truetype('arial.ttf', size=fz))
#         draw.text(xy=(10, 75), text=str(i + 1), fill='black', font=ImageFont.truetype('arial.ttf', size=18))
#         bg.paste(im, (2 * (i % 5 + 1) + 300 * (i % 5),
#                       2 * (i // 5 + 1) + 100 * (i // 5)))
#     output = io.BytesIO()
#     bg.save(output, format='JPEG')
#     res = requests.post(url='https://api.imgbb.com/1/upload',
#                         params={'key': imgbb_token},
#                         files={'image': output.getvalue()})
#     cbg = Image.new('RGB', (1512, 512), (246, 79, 23))
#     for i in range(25):
#         word = codewords[i]
#         bgcolor = (44, 44, 44) if word.mode == 'b' else (255, 255, 255) if word.mode == 'w' else (255, 64, 50) \
#             if word.mode == 'r' else (50, 176, 255)
#         color = (255, 255, 255) if word.mode == 'b' else (0, 0, 0)
#         im = Image.new('RGB', (300, 100), bgcolor)
#         draw = ImageDraw.Draw(im)
#         w, h = draw.textsize(text=word.text, font=ImageFont.truetype('arial.ttf', size=word.fz))
#         x, y = (300 - w) / 2, (100 - h) / 2
#         draw.text(xy=(x, y), text=word.text, fill=color, font=ImageFont.truetype('arial.ttf', size=word.fz))
#         draw.text(xy=(10, 75), text=str(i + 1), fill=color, font=ImageFont.truetype('arial.ttf', size=18))
#         cbg.paste(im, (2 * (i % 5 + 1) + 300 * (i % 5),
#                        2 * (i // 5 + 1) + 100 * (i // 5)))
#     return bg, cbg
#
#
# class MyClass:
#     def __init__(self):
#         self.id = 1
#
#     async def run(self):
#         print(self.id)
#
#
# class Codenames:
#     def __init__(self, ctx):
#         self._ctx = ctx
#         self.client = ctx.bot
#         self._guild = ctx.guild
#         self._channel = ctx.message.channel
#         self._creator = ctx.message.author
#         self._words = [Word(_, random.choice(words)) for _ in range(25)]
#         random.shuffle(self._words)
#         self._bg, self._cbg = bg_create(self._words)
#         self._bg_fp = str(self._guild.id) + ''.join(random.choice('abcdefghijklmnopq') for _ in range(5)) + '.jpg'
#         self._cbg_fp = str(self._guild.id) + ''.join(random.choice('abcdefghijklmnopq') for _ in range(5)) + '.jpg'
#         self._msg = None
#
#     async def play_(self):
#         self._bg.save(self._bg_fp, 'JPEG')
#         # self._cbg.save(self._cbg_fp, 'JPEG')
#         # embed = discord.Embed(color=discord.Colour.from_rgb(255, 250, 205))
#         # embed.set_image(url=self._bg_fp)
#         self._msg = await self._ctx.send(file=discord.File(self._bg_fp))
#         # await self._ctx.send(file=discord.File(self._cbg_fp))
#         while True:
#             message = await self.client.wait_for('message', check=self.check_author(self._ctx.message.author))
#             i = int(message.content) - 1
#             word = self._words[i]
#             bgcolor = (44, 44, 44) if word.mode == 'b' else (255, 255, 255) if word.mode == 'w' else (255, 64, 50) \
#                 if word.mode == 'r' else (50, 176, 255)
#             color = (255, 255, 255) if word.mode == 'b' else (0, 0, 0)
#             im = Image.new('RGB', (300, 100), bgcolor)
#             draw = ImageDraw.Draw(im)
#             w, h = draw.textsize(text=word.text, font=ImageFont.truetype('arial.ttf', size=word.fz))
#             x, y = (300 - w) / 2, (100 - h) / 2
#             draw.text(xy=(x, y), text=word.text, fill=color, font=ImageFont.truetype('arial.ttf', size=word.fz))
#             draw.text(xy=(10, 75), text=str(i + 1), fill=color, font=ImageFont.truetype('arial.ttf', size=18))
#             self._bg.paste(im, (2 * (i % 5 + 1) + 300 * (i % 5),
#                            2 * (i // 5 + 1) + 100 * (i // 5)))
#             output = io.BytesIO()
#             self._bg.save(self._bg_fp, format='JPEG')
#             # res = requests.post(url='https://api.imgbb.com/1/upload',
#             #                     params={'key': imgbb_token},
#             #                     files={'image': output.getvalue()})
#             # embed = discord.Embed(color=discord.Colour.from_rgb(255, 250, 205))
#             # embed.set_image(url=res.json()['data']['url'])
#             await self._msg.delete()
#             self._msg = await self._ctx.send(file=discord.File(self._bg_fp))
#             # await self._ctx.send(self._words[int(message.content)-1].text)
#
#     @staticmethod
#     def check_author(author):
#         def inner_check(message):
#             if message.author != author:
#                 return False
#             if message.content.startswith('.m.f'):
#                 raise asyncio.TimeoutError
#             try:
#                 return True if 1 <= int(message.content) <= 25 else False
#             except ValueError:
#                 return False
#
#         return inner_check


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
            print(f'=== res for upload: {res}')
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
                        ':arrow_up:`.e.u`,`.upload` - отправь с командой картинку и я отправлю тебе ссылку на это '
                        'изображение. Очень удобно если хочется поделиться картинкой, но без отправления файла.'

        )
        embed.set_author(name='Развлекательные команды',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)


def setup(client):
    client.add_cog(Enter(client))
