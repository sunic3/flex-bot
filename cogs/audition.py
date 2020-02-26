import discord
from discord.ext import commands
from discord.ext.commands import has_permissions

from cogs.bot import channel_check, ChannelException

import lyricsgenius
from cfg import genius_token
from cfg import youtube_token as ytt
from bottools import postix, wordend, data_read, data_write, yt_search, yt_request, yt_playlist, channels_perms, exp

import os
import re
import asyncio
import itertools
import sys
import json
import time
import random
import datetime
import typing
from math import floor
import youtube_dl
from async_timeout import timeout
from functools import partial
from collections import Counter, OrderedDict
import traceback

ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpegopts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdlopts)

ytts = ytt


def lyrics(name):
    try:
        genius = lyricsgenius.Genius(genius_token)
        song = genius.search_song(re.sub(r'[\[\(].+[\]\)]', '', name))
        if song is None:
            return f"Слова песни {name} не найдены"
        return f'\n{song.lyrics}'
    except Exception as e:
        return f"Слова песни {name} не найдены"


def view_mod(n: int):
    if n > 10000000000:
        return str(floor(n / 1000000000)) + ' млрд.'
    if n > 1000000000:
        n = list(str(floor(n / 100000000)))
        return '.'.join(n) + ' млрд.' if n[-1] != '0' else n[0] + ' млрд.'
    if n > 10000000:
        return str(floor(n / 1000000)) + ' млн.'
    if n > 1000000:
        n = list(str(floor(n / 100000)))
        return '.'.join(n) + ' млн.' if n[-1] != '0' else n[0] + ' млн.'
    if n > 10000:
        return str(floor(n / 1000)) + ' тыс.'
    if n > 1000:
        n = list(str(floor(n / 100)))
        return '.'.join(n) + ' тыс.' if n[-1] != '0' else n[0] + ' тыс.'
    return str(n)


def check_dj(ctx):
    dj = data_read(ctx.guild)['dj']
    return not dj or dj in [role.id for role in ctx.message.author.roles]


def check_music(ctx):
    m = data_read(ctx.guild)['music_id']
    if m and ctx.channel.id != m:
        raise MusicChannelError
    return


class VoiceConnectionError(commands.CommandError):
    pass


class MusicChannelError(commands.CommandError):
    async def do(self, ctx, client):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        c = discord.utils.get(client.get_all_channels(), id=data_read(ctx.guild)['music_id'])
        await ctx.send(f'Этот канал не для музыки :frowning2:\nпопробуй написать в {c.mention}', delete_after=5)


class InvalidVoiceChannel(VoiceConnectionError):
    pass


class CommandInvokeError(youtube_dl.utils.DownloadError):
    async def something(self, ctx):
        ctx.send("Это видео недоступно")


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, src, *, data):
        super().__init__(source)
        self.src = src
        self.data = data

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')

    def __getitem__(self, item: str):
        return self.__getattribute__(item)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        loop = loop or asyncio.get_event_loop()
        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        new_data = await loop.run_in_executor(None, to_run)
        return cls(discord.FFmpegPCMAudio(new_data['url'], **ffmpegopts), src=data,
                   data=new_data)


class MusicPlayer:
    __slots__ = ('client', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'dy')

    def __init__(self, ctx):
        self.client = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None
        self.volume = .5
        self.current = None

        self.dy = True
        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.client.wait_until_ready()

        while not self.client.is_closed() and self.dy:
            self.next.clear()
            try:
                async with timeout(600):
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                if self._guild.voice_client is not None and self.dy:
                    await self._channel.send('Отключаюсь из-за отсутствия флекса :unamused:', delete_after=40)
                    return self.destroy(self._guild)
                return

            if not isinstance(source, YTDLSource):
                if self._guild.voice_client is not None:
                    try:
                        source = await YTDLSource.regather_stream(source, loop=self.client.loop)
                    except Exception:
                        await self._channel.send(f'```css\nОшибка воспроизведения песни {source["title"]}\n```')
                        continue
                else:
                    try:
                        msg = await self._channel.fetch_message(source['id'])
                        await msg.delete()
                    except discord.HTTPException:
                        pass
                    except AttributeError:
                        pass
                    continue
            source.volume = self.volume
            self.current = source
            try:
                self._guild.voice_client.play(source,
                                              after=lambda _: self.client.loop.call_soon_threadsafe(self.next.set))
                d = data_read(self._guild)
                if d['now']:
                    self.np = await self._channel.send(f':loud_sound: сейчас играет **`{self.current.title}`**')
            except AttributeError:
                try:
                    msg = await self._channel.fetch_message(source.src['id'])
                    await msg.delete()
                except discord.HTTPException:
                    pass
                except AttributeError:
                    pass
                source.cleanup()
                self.current = None
                continue
            d = data_read(self._guild)
            d['current'] = time.time()
            data_write(self._guild, d)
            with open(f'{self._guild.id}/history.json', 'r') as f:
                d = json.load(f)
                d.append([f'{source.title}', source.src['requester'].id])
                if len(d) > 1000:
                    del d[0]
            with open(f'{self._guild.id}/history.json', 'w') as f:
                json.dump(d, f, indent=4, sort_keys=True)
            try:
                await self.queue.put(await self._cog.queues[self._guild.id].pop())
                await self._cog.queues[self._guild.id].prepare()
            except IndexError:
                pass
            await self.next.wait()
            try:
                await self.np.delete()
            except Exception:
                pass
            try:
                msg = await self._channel.fetch_message(self.current.src['id'])
                await msg.delete()
            except discord.HTTPException:
                pass
            except AttributeError:
                pass
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        return self.client.loop.create_task(self._cog.cleanup(guild))


class MusicQueue(list):
    def __init__(self, player: MusicPlayer):
        super(MusicQueue, self).__init__()
        self.player = player

    async def pop(self):
        e = super(MusicQueue, self).pop(0)
        return e

    async def put(self, e):
        if self.player.queue.qsize() == 0:
            e = await YTDLSource.regather_stream(e, loop=self.player.client.loop)
            await self.player.queue.put(e)
            return
        if self.__len__() == 0:
            e = await YTDLSource.regather_stream(e, loop=self.player.client.loop)
        super(MusicQueue, self).append(e)

    async def prepare(self):
        if self.__len__() > 0:
            e = super(MusicQueue, self).pop(0)
            if not isinstance(e, YTDLSource):
                e = await YTDLSource.regather_stream(e, loop=self.player.client.loop)
            super(MusicQueue, self).insert(0, e)


class Music(commands.Cog):
    __slots__ = ('client', 'players', 'queues', 'members')

    def __init__(self, client):
        self.client = client
        self.players = {}
        self.queues = {}
        self.members = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass
        try:
            del self.players[guild.id]
            del self.queues[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Ошибка подключения к голосовому каналу.\n'
                           'Убедись что ты находишься хотя бы в одном :hugging:')

        elif isinstance(error, commands.errors.CommandNotFound):
            await ctx.message.delete()
            await ctx.send(f'Неизвестная команда {ctx.message.content} :thinking:')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player
            self.queues[ctx.guild.id] = MusicQueue(player)

        return player

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot:
            d = data_read(member.guild)
            if d['notice']:
                try:
                    if before.channel is None:
                        self.members[member.id] = time.time()
                    if after.channel is None:
                        s = round(time.time() - self.members[member.id])
                        txt = f'{s // 3600} час{wordend(s // 3600)}, {s // 60  % 60:02} ' \
                            f'минут{wordend(s // 60 % 60, "у", "ы", "")}' \
                            f' и {s % 60} секунд{wordend(s % 60, "у", "ы", "")}'\
                            if s // 3600 != 0 else \
                            f'{s // 60} минут{wordend(s // 60, "у", "ы", "")} и {s % 60} ' \
                            f'секунд{wordend(s % 60, "у", "ы", "")}' \
                            if s // 60 != 0 else f'{s} секунд{wordend(s, "у", "ы", "")}'
                        end = 'ие' if txt[0] != '1 ' else 'ий' if len(txt) > 22 else 'ую'
                        await discord.utils.get(self.client.get_all_channels(), id=channels_perms(member.guild)).send(
                            content=f'Спасибо {member.mention} за лучш{end} {txt} в нашей жизни!', delete_after=10)
                except KeyError:
                    pass
            vc = list(filter(lambda e: e.guild.id == member.guild.id, self.client.voice_clients))
            if len(vc) < 1:
                return
            if not vc[0] or not vc[0].is_connected():
                return
            if len(list(filter(lambda e: not e.bot, before.channel.members))) == 0:
                try:
                    player = self.players[member.guild.id]
                    queue = self.queues[member.guild.id]
                    self.queues[member.guild.id] = MusicQueue(player)
                    await self.cleanup(member.guild)
                    try:
                        if player.queue.qsize() > 0:
                            track = await player.queue.get()
                            if track.src['id']:
                                for channel in member.guild.text_channels:
                                    try:
                                        msg = await channel.fetch_message(track.src['id'])
                                        await msg.delete()
                                    except discord.errors.NotFound:
                                        pass
                            for _ in range(len(queue)):
                                if isinstance(queue[0], YTDLSource):
                                    track = (await queue.pop()).src
                                    if track['id']:
                                        for channel in member.guild.text_channels:
                                            try:
                                                msg = await channel.fetch_message(track['id'])
                                                await msg.delete()
                                            except discord.errors.NotFound:
                                                pass
                                else:
                                    track = await queue.pop()
                                    if track['id']:
                                        for channel in member.guild.text_channels:
                                            try:
                                                msg = await channel.fetch_message(track['id'])
                                                await msg.delete()
                                            except discord.errors.NotFound:
                                                pass
                    except IndexError:
                        pass
                    finally:
                        player.dy = False
                except KeyError:
                    pass

    @commands.command(name='music', aliases=['m'])
    @has_permissions(administrator=True)
    async def music_channel_(self, ctx):
        channel_check(ctx)
        await ctx.message.delete()
        d = data_read(ctx.guild)
        d['music_id'] = ctx.channel.id
        data_write(ctx.guild, d)
        await ctx.send(f'Канал {ctx.channel.mention} установлен как музыкальный :musical_note:', delete_after=20)

    @music_channel_.error
    async def music_channel_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.message.delete()
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=10)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        else:
            await exp(ctx)

    @commands.command(name='dj')
    @has_permissions(administrator=True)
    async def dj_(self, ctx, a: typing.Union[discord.Role, discord.Member]):
        channel_check(ctx)
        await ctx.message.delete()
        d = data_read(ctx.guild)
        if isinstance(a, discord.Role):
            d['dj'] = a.id
            data_write(ctx.guild, d)
        else:
            if d['dj']:
                try:
                    await a.add_roles(discord.utils.get(ctx.guild.roles, id=d['dj']))
                except discord.Forbidden:
                    await ctx.send('У меня недостаточно прав. В настройках сервера моя роль должна быть выше '
                                   'используемых ролей :pleading_face:', delete_after=40)
                except AttributeError:
                    await ctx.send('Я не могу найти на сервере роль ДиДжея. Попробуй установить ее заново'
                                   ' :kissing_smiling_eyes:', delete_after=20)
            else:
                await ctx.send('Роль для ДиДжея не установлена :woman_shrugging:', delete_after=20)

    @dj_.error
    async def dj_error(self, ctx, error):
        if isinstance(error, commands.errors.MissingPermissions):
            await ctx.message.delete()
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=10)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        else:
            await exp(ctx)

    @commands.command(name='join', aliases=['j'])
    async def connect_(self, ctx):
        try:
            channel = ctx.author.voice.channel
            vc = ctx.voice_client
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

            if vc:
                if vc.channel.id == channel.id:
                    return
                try:
                    await vc.move_to(channel)
                except asyncio.TimeoutError:
                    raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
            else:
                try:
                    await channel.connect()
                except asyncio.TimeoutError:
                    raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

        except AttributeError:
            raise InvalidVoiceChannel

    @commands.check(check_dj)
    @commands.command(name='play', aliases=['flex', 'p'])
    async def play_(self, ctx, *, search: str):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        channel_check(ctx)
        check_music(ctx)
        await ctx.trigger_typing()
        try:
            vc = ctx.voice_client
            player = self.get_player(ctx)

            if not vc:
                await ctx.invoke(self.connect_)

            queue = player.queue.qsize() + 1 if vc and vc.is_playing() else 'В процессе'
            if re.fullmatch(r'https://www.youtube.com/watch\?v=[0-9a-zA-Z_\-]+', search):
                pk = re.match(r'https://www.youtube.com/watch\?v=([0-9a-zA-Z_\-]+)', search).groups()[0]
            else:
                sk = {}
                msg_logs = []
                while not sk:
                    try:
                        async with timeout(5):
                            sk = yt_search(search, 'snippet', 1, 'video')
                    except ConnectionResetError:
                        msg_log = await ctx.send('Проблемы с подключением к Youtube :link:\n'
                                                 'Попытка создать новое соединение :wrench:')
                        msg_logs.append(msg_log)
                    except asyncio.TimeoutError:
                        continue
                result = sk.get("items", [])[0]
                pk = result["id"]["videoId"]
            try:
                res = yt_request('https://www.googleapis.com/youtube/v3/videos',
                                 params={
                                     'id': pk,
                                     'part': 'snippet,contentDetails,statistics'
                                 }).json()["items"][0]
            except KeyError:
                await ctx.send(f'По запросу {search} ничего не найдено :weary:\n')
            t = re.findall(r'\d+', res["contentDetails"]["duration"])
            if len(t) == 1:
                duration = f'0:{t[0] if len(t[0]) > 1 else "0" + t[0]}'
            else:
                for i in range(1, len(t)):
                    if len(t[i]) != 2:
                        t[i] = '0' + t[i]
                duration = ':'.join(t)
            embed = discord.Embed(
                title=res['snippet']['title'],
                url=f'https://www.youtube.com/watch?v={pk}',
                colour=ctx.message.author.colour
            )
            embed.set_author(name=ctx.message.author.display_name + f' добавил{postix(ctx)} песню',
                             icon_url=ctx.message.author.avatar_url)
            embed.add_field(name='ДиДжей', value=ctx.message.author.mention, inline=True)
            embed.add_field(name='Время', value=duration)
            embed.add_field(name='Очередь', value=str(queue))
            embed.add_field(name='Канал',
                            value=f"[{res['snippet']['channelTitle']}]"
                            f"(https://www.youtube.com/channel/{res['snippet']['channelId']})")
            embed.add_field(name='Релиз', value=datetime.datetime.strptime(
                res['snippet']['publishedAt'].split('T')[0], '%Y-%m-%d').strftime('%d.%m.%y'))
            embed.add_field(name='Просмотров', value=view_mod(int(res['statistics']['viewCount'])))
            try:
                embed.set_image(url=res["snippet"]["thumbnails"]["maxres"]["url"])
            except KeyError:
                try:
                    embed.set_image(url=res["snippet"]["thumbnails"]["standard"]["url"])
                except KeyError:
                    try:
                        embed.set_image(url=res["snippet"]["thumbnails"]["high"]["url"])
                    except KeyError:
                        pass
            msg = await ctx.send(embed=embed)
            msge = msg.id

            source = {'webpage_url': f'https://www.youtube.com/watch?v={pk}', 'requester': ctx.author,
                      'title': res['snippet']['title'], 'id': msge,
                      'key': ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(6)), 'pl': ''}
            await self.queues[ctx.guild.id].put(source)
        except youtube_dl.DownloadError:
            await ctx.send(f'Ошибка воспроизведения. Возможно, данной песни не существует '
                           f'или она запрещена на территории твоей страны :mag_right:', delete_after=40)

    @play_.error
    async def play_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:', delete_after=40)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        elif isinstance(error, MusicChannelError):
            await error.do(ctx, self.client)
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Ошибка подключения к голосовому каналу.\n'
                           'Убедись что ты находишься хотя бы в одном :hugging:', delete_after=40)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'`{ctx.message.author.name}` ты забыл{postix(ctx)} ввести название песни :slight_smile:',
                           delete_after=20)
            await asyncio.sleep(10)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
        else:
            await exp(ctx)

    @commands.check(check_dj)
    @commands.command(name='search', aliases=['f', 'find'])
    async def search_(self, ctx, *, query: str):
        channel_check(ctx)
        check_music(ctx)
        await ctx.trigger_typing()
        sk = {}
        msg_logs = []
        c = data_read(ctx.guild)["count"]
        while not sk:
            try:
                async with timeout(5):
                    sk = yt_search(query, 'snippet', c, 'video')
            except ConnectionResetError:
                msg_log = await ctx.send('Проблемы с подключением к Youtube :link:\n'
                                         'Попытка создать новое соединение :wrench:')
                msg_logs.append(msg_log)
            except asyncio.TimeoutError:
                continue
        results = sk.get("items", [])
        videos, ids, durations = [], [], []
        for result in results:
            if result['id']['kind'] == "youtube#video":
                videos.append('[{}]({})'.format(result["snippet"]["title"]
                                                .replace("&amp;", "&").replace("&quot;", "\"").replace("&#39;", "`"),
                                                "https://www.youtube.com/watch?v=" + result["id"]["videoId"]))
                ids.append(str(result["id"]["videoId"]))
        res = yt_request('https://www.googleapis.com/youtube/v3/videos',
                         params={
                             'id': ','.join(ids),
                             'part': 'snippet,contentDetails,statistics'
                         })
        for res in res.json()["items"]:
            t = re.findall(r'\d+', res["contentDetails"]["duration"])
            if len(t) == 1:
                durations.append(f'0:{t[0] if len(t[0]) > 1 else "0" + t[0]}')
                continue
            for i in range(1, len(t)):
                if len(t[i]) != 2:
                    t[i] = '0' + t[i]
            durations.append(':'.join(t))
        embed = discord.Embed(color=ctx.message.author.colour)
        embed.add_field(name=f'Результаты поиска для "{query}":',
                        value='\n'.join(list(f'**{videos.index(video) + 1}**. {video} '
                                             f'`[{durations[videos.index(video)]}]`' for video in videos))
                        )
        await ctx.send(embed=embed, delete_after=60)
        for msg_log in msg_logs:
            await msg_log.delete()
        try:
            message = await self.client.wait_for('message', check=self.check_author(ctx.message.author), timeout=60)
            n = int(message.content)
            search = re.findall(r'\(([^\(\)]+)\)', videos[n - 1])
            await message.delete()
            await ctx.invoke(self.play_, search=search[-1])
        except asyncio.TimeoutError:
            return
        except Exception:
            await exp(ctx)

    @search_.error
    async def search_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.message.delete()
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:', delete_after=40)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        elif isinstance(error, MusicChannelError):
            await error.do(ctx, self.client)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'`{ctx.message.author.name}` ты забыл{postix(ctx)} ввести название песни :slight_smile:',
                           delete_after=40)
            await asyncio.sleep(5)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
        else:
            await exp(ctx)

    @commands.check(check_dj)
    @commands.command(name='playlist', aliases=['pl'])
    async def playlist_(self, ctx, *, query):
        channel_check(ctx)
        check_music(ctx)
        try:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            vc = ctx.voice_client
            player = self.get_player(ctx)
            if not vc:
                await ctx.invoke(self.connect_)
            if query.startswith('-r '):
                shuffle = True
                query = query[3:]
            else:
                shuffle = False
            await ctx.trigger_typing()
            c = data_read(ctx.guild)['count']
            try:
                pl = re.findall(r'list=([^&]+)', query)[0]
            except IndexError:
                sk = yt_search(query, 'snippet', c, 'playlist')
                results = sk.get("items", [])
                pls, ids, counts = [], [], []
                for result in results:
                    pls.append('[{}]({})'.format(result["snippet"]["title"]
                                                 .replace("&amp;", "&").replace("&quot;", "\"")
                                                 .replace("&#39;", "`"),
                                                 "https://www.youtube.com/playlist?list=" + result["id"]["playlistId"]
                                                 ))
                    ids.append(str(result["id"]["playlistId"]))
                res = yt_request('https://www.googleapis.com/youtube/v3/playlists',
                                 params={
                                     'id': ','.join(ids),
                                     'part': 'contentDetails'
                                 })
                for res in res.json()["items"]:
                    counts.append(res['contentDetails']['itemCount'])
                embed = discord.Embed(color=ctx.message.author.colour)
                embed.add_field(name=f'Результаты поиска для "{query}":',
                                value='\n'.join(list(f'**{pls.index(video) + 1}**. {video} '
                                                     f'`[{counts[pls.index(video)]}]`' for video in pls))
                                )
                await ctx.send(embed=embed, delete_after=60)
                try:
                    message = await self.client.wait_for('message', check=self.check_author(ctx.message.author))
                    n = int(message.content)
                    pl = re.findall(r'\(([^\(\)]+)\)', pls[n - 1])[-1].split('list=')[-1]
                    await message.delete()
                except asyncio.TimeoutError:
                    return
                except Exception:
                    pass
            pagetoken, titles, duration, uniq = '', [], 0, {}
            sk = yt_playlist('snippet,contentDetails', pl)
            key = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(6))
            await ctx.trigger_typing()
            while True:
                tmp_titles = []
                res = yt_request('https://www.googleapis.com/youtube/v3/playlistItems',
                                 params={
                                     'part': 'snippet,contentDetails,status,id',
                                     'playlistId': pl,
                                     'maxResults': 50,
                                     'pageToken': pagetoken
                                 })
                for r in res.json()["items"]:
                    tmp_titles.append([f'https://www.youtube.com/watch?v={r["contentDetails"]["videoId"]}',
                                   r["snippet"]["title"]])
                if shuffle:
                    random.shuffle(tmp_titles)
                titles += tmp_titles
                if 'prevPageToken' not in res.json().keys():
                    source = {'webpage_url': titles[0][0], 'requester': ctx.author, 'title': titles[0][1],
                              'id': None, 'key': key, 'pl': sk['items'][0]['snippet']['title']}
                    await self.queues[ctx.guild.id].put(source)
                if 'nextPageToken' in res.json().keys():
                    pagetoken = res.json()['nextPageToken']
                else:
                    break
            queue = str(player.queue.qsize() + 1) if vc and vc.is_playing() else 'В процессе'
            embed = discord.Embed(
                title=sk['items'][0]['snippet']['title'],
                url=f'https://www.youtube.com/playlist?list={pl}',
                colour=ctx.message.author.colour
            )
            embed.set_author(name=ctx.message.author.display_name + f' добавил{postix(ctx)} плейлист',
                             icon_url=ctx.message.author.avatar_url)
            embed.add_field(name='ДиДжей', value=ctx.message.author.mention, inline=True)
            embed.add_field(name='Количество', value=str(len(titles)) + f' трек{wordend(len(titles))}')
            embed.add_field(name='Очередь', value=queue)
            try:
                embed.set_image(url=sk["items"][0]["snippet"]["thumbnails"]["maxres"]["url"])
            except KeyError:
                try:
                    embed.set_image(url=sk["items"][0]["snippet"]["thumbnails"]["standard"]["url"])
                except KeyError:
                    try:
                        embed.set_image(url=sk["items"][0]["snippet"]["thumbnails"]["high"]["url"])
                    except KeyError:
                        pass
            msg = await ctx.send(embed=embed)
            msge = msg.id
            if shuffle:
                random.shuffle(titles)
            for t in titles[1:-1]:
                source = {'webpage_url': t[0], 'requester': ctx.author, 'title': t[1],
                          'id': None, 'key': key, 'pl': sk['items'][0]['snippet']['title']}
                await self.queues[ctx.guild.id].put(source)
            source = {'webpage_url': titles[-1][0], 'requester': ctx.author, 'title': titles[-1][1],
                      'id': msge, 'key': key, 'pl': sk['items'][0]['snippet']['title']}
            await self.queues[ctx.guild.id].put(source)

        except InvalidVoiceChannel:
            await ctx.send('Ошибка подключения к голосовому каналу.\n'
                           'Убедись что ты находишься хотя бы в одном :hugging:', delete_after=40)
        except Exception:
            await exp(ctx)

    @playlist_.error
    async def playlist_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.message.delete()
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:', delete_after=40)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        elif isinstance(error, MusicChannelError):
            await error.do(ctx, self.client)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'`{ctx.message.author.name}` ты забыл{postix(ctx)} ввести название песни :slight_smile:',
                           delete_after=40)
            await asyncio.sleep(5)
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

    @commands.check(check_dj)
    @commands.command(name='playlist_skip', aliases=['ps'])
    async def playlist_skip_(self, ctx):
        channel_check(ctx)
        check_music(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('В очереди нет песен для воспроизвдения :mailbox_with_no_mail:', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return
        vc.pause()
        await ctx.message.delete()
        player = self.players[ctx.guild.id]
        ck = player.current
        if not ck.src["pl"]:
            await ctx.invoke(self.skip_)
        try:
            if player.queue.qsize() > 0:
                track = await player.queue.get()
                if track.src["key"] == ck.src["key"]:
                    if track.src['id']:
                        try:
                            msg = await ctx.channel.fetch_message(track.src['id'])
                            await msg.delete()
                        except discord.HTTPException:
                            pass
                else:
                    await player.queue.put(track)
                    await ctx.send(f':warning: **`{ctx.author.name}`** скипнул плейлист :fast_forward: '
                                   f'**`{self.players[ctx.guild.id].current.src["pl"]}`**', delete_after=15)
                    raise IndexError
                queue = self.queues[ctx.guild.id]
                for _ in range(len(queue)):
                    if isinstance(queue[0], YTDLSource):
                        if queue[0].src['key'] == ck.src['key']:
                            track = (await queue.pop()).src
                            if track['id']:
                                try:
                                    msg = await ctx.channel.fetch_message(track['id'])
                                    await msg.delete()
                                except discord.HTTPException:
                                    pass
                        else:
                            await ctx.send(f':warning: **`{ctx.author.name}`** скипнул плейлист :fast_forward: '
                                           f'**`{self.players[ctx.guild.id].current.src["pl"]}`**', delete_after=15)
                            await queue.prepare()
                            await player.queue.put(await queue.pop())
                            break
                    else:
                        if queue[0]['key'] == ck.src['key']:
                            track = await queue.pop()
                            if track['id']:
                                try:
                                    msg = await ctx.channel.fetch_message(track['id'])
                                    await msg.delete()
                                except discord.HTTPException:
                                    pass
                        else:
                            await ctx.send(f':warning: **`{ctx.author.name}`** скипнул плейлист :fast_forward: '
                                           f'**`{self.players[ctx.guild.id].current.src["pl"]}`**', delete_after=15)
                            await queue.prepare()
                            await player.queue.put(await queue.pop())
                            break
        except IndexError:
            pass

        vc.stop()

    @playlist_skip_.error
    async def playlist_skip_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:')
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        elif isinstance(error, MusicChannelError):
            await error.do(ctx, self.client)
        else:
            await exp(ctx)

    @commands.command(name='pause')
    async def pause_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('Чтобы поставить музыку на пузу, нужно её сначала включить :wink:\n'
                                  'Используй команду `.flex для этого.`', delete_after=40)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f':pause_button: **`{ctx.author.name}`** поставил{postix(ctx)} песню на паузу')

    @commands.command(name='resume')
    async def resume_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('В очереди нет песен для воспроизвдения :mailbox_with_no_mail:', delete_after=20)
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Resumed the song!')

    @commands.check(check_dj)
    @commands.command(name='skip', aliases=['s'])
    async def skip_(self, ctx):
        channel_check(ctx)
        check_music(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('В очереди нет песен для воспроизвдения :mailbox_with_no_mail:', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        await ctx.message.delete()
        await ctx.send(f':warning: **`{ctx.author.name}`** скипнул{postix(ctx)} песню :fast_forward: '
                       f'**`{self.players[ctx.guild.id].current.title}`**', delete_after=15)

        vc.stop()

    @skip_.error
    async def skip_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:')
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        elif isinstance(error, MusicChannelError):
            await error.do(ctx, self.client)
        else:
            await exp(ctx)

    @commands.command(name='queue', aliases=['q'])
    async def queue_info(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            await ctx.message.delete()
            return await ctx.send(f'Ты меня не даже пригласил{postix(ctx)} на голосовой канал :cry:', delete_after=20)

        player = self.get_player(ctx)
        if player.queue.empty():
            await ctx.message.delete()
            return await ctx.send('Очередь пуста :mailbox_with_no_mail:')

        upcoming = list(itertools.islice(player.queue._queue, 0, player.queue.qsize())) + self.queues[ctx.guild.id]
        tracks, all = OrderedDict(), 0
        for track in upcoming:
            all += 1
            if isinstance(track, YTDLSource):
                track = track.src
            if track['pl'] and track['key'] in tracks.keys():
                tracks[track['key']][1] += 1
            elif track['pl']:
                tracks[track['key']] = [track['pl'], 1]
            else:
                tracks[track['key']] = track['title']
            if len(tracks) == 5:
                break
        fmt = []
        for v in tracks.values():
            if isinstance(v, str):
                fmt.append(f'**{v}**')
            else:
                fmt.append(f'*{v[0]}* `[ещё {v[1]} трек{wordend(v[1])}]`')
        embed = discord.Embed(title=f'На очереди  - всего {len(upcoming)} трек{wordend(len(upcoming))}',
                              description='\n'.join(f'{i + 1}. {fmt[i]}' for i in range(len(fmt))))
        if len(upcoming) - all:
            embed.set_footer(text=f'И ещё {len(upcoming) - all} трек{wordend(len(upcoming) - all)}')
        await ctx.message.delete()
        await ctx.send(embed=embed)

    @commands.check(check_dj)
    @commands.command(name='queue_clean', aliases=['qc'])
    async def queue_clean_(self, ctx):
        channel_check(ctx)
        check_music(ctx)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('В очереди нет песен :mailbox_with_no_mail:', delete_after=20)

        await ctx.message.delete()
        player = self.players[ctx.guild.id]
        msgid = 0 if player.current.src['id'] else 1
        try:
            if player.queue.qsize() > 0:
                track = await player.queue.get()
                if track.src["id"] and not msgid:
                    try:
                        msg = await ctx.channel.fetch_message(track.src['id'])
                        await msg.delete()
                    except discord.HTTPException:
                        pass
                elif track.src["id"]:
                    msgid *= 0
                    player.current.src["id"] = track.src["id"]
                queue = self.queues[ctx.guild.id]
                self.queues[ctx.guild.id] = MusicQueue(player)
                await ctx.send('Очередь очищена :broom:', delete_after=10)
                for _ in range(len(queue)):
                    if isinstance(queue[0], YTDLSource):
                        track = (await queue.pop()).src
                        if track['id'] and not msgid:
                            try:
                                msg = await ctx.channel.fetch_message(track['id'])
                                await msg.delete()
                            except discord.HTTPException:
                                pass
                        elif track['id']:
                            msgid *= 0
                            player.current.src["id"] = track["id"]
                    else:
                        track = await queue.pop()
                        if track['id'] and not msgid:
                            try:
                                msg = await ctx.channel.fetch_message(track['id'])
                                await msg.delete()
                            except discord.HTTPException:
                                pass
                        elif track['id']:
                            msgid *= 0
                            player.current.src["id"] = track["id"]
                await ctx.send('Очередь очищена :broom:', delete_after=10)
            else:
                await ctx.send('В очереди нет песен :mailbox_with_no_mail:', delete_after=20)
                return
        except IndexError:
            pass

    @queue_clean_.error
    async def queue_clean_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:')
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        elif isinstance(error, MusicChannelError):
            await error.do(ctx, self.client)
        else:
            await exp(ctx)

    @commands.command(name='now_playing', aliases=['np', 'current', 'now'])
    async def now_playing_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send(f'Ты меня не даже пригласил{postix(ctx)} на голосовой канал :cry:', delete_after=40)

        player = self.get_player(ctx)
        await ctx.message.delete()

        if not player.current:
            return await ctx.send('Добавь музыку для флекса при помощи команды `.flex` :dancer:', delete_after=20)

        with open(f"{ctx.guild.id}/data.json", 'r') as f:
            d = json.load(f)
        dt = round(time.time() - d['current'])
        final = player.current.data['duration']
        per = round(dt / final * 100)
        per_style = per * 7 // 10
        embed_time = '{:02}:{:02}:{:02} из {:02}:{:02}:{:02}' \
            .format(dt // 3600, dt // 60 % 60, dt % 60, final // 3600, final // 60 % 60, final % 60) \
            if final >= 3600 else '{:02}:{:02} из {:02}:{:02}' \
            .format(dt // 60 % 60, dt % 60, final // 60 % 60, final % 60) if final >= 600 else \
            '{}:{:02} из {}:{:02}'.format(dt // 60 % 60, dt % 60, final // 60 % 60, final % 60)

        embed = discord.Embed(colour=ctx.message.author.colour,
                              description=f'[{player.current.title}]({player.current.web_url})\n'
                              f'**|{"-" * per_style}{per}%{"-" * (70 - per_style)}|**```ini\n[{embed_time}]```', )
        embed.set_author(name='Сейчас играет')
        # embed.set_thumbnail(url=player.current.data['thumbnail'])
        # embed.set_thumbnail(url='https://thumbs.gfycat.com/AnchoredFlamboyantGuppy-size_restricted.gif')
        try:
            await player.np.delete()
        except discord.HTTPException:
            pass
        except AttributeError:
            pass
        player.np = await ctx.send(embed=embed, delete_after=final)

    @commands.command(name='lyrics', aliases=['t', 'text'])
    async def lyrics_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client
        await ctx.trigger_typing()

        if not vc or not vc.is_connected():
            return await ctx.send(f'Ты меня не даже пригласил{postix(ctx)} на голосовой канал :cry:', delete_after=40)

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('Добавь музыку для флекса при помощи команды `.flex` :dancer:', delete_after=20)
        await ctx.send(f':mag_right: ищу текст песни `{vc.source.title}`...')
        lyric = lyrics(vc.source.title)
        await ctx.message.delete()
        [await ctx.send(lyric[x:x + 2000], delete_after=3600) for x in range(0, len(lyric), 2000)]

    @commands.check(check_dj)
    @commands.command(name='volume', aliases=['vol', 'm.v'])
    async def change_volume(self, ctx, *, vol: float):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client
        await ctx.message.delete()

        if not vc or not vc.is_connected():
            return await ctx.send('Добавь музыку для флекса при помощи команды `.flex` :dancer:', delete_after=20)

        if not 0 < vol < 101:
            return await ctx.send('Введи число от :one: до :100: пожалуйста', delete_after=20)

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(f'**`{ctx.author.name}`** изменил громкость до **{vol}%**', delete_after=10)

    @change_volume.error
    async def change_volume_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:')
        else:
            await exp(ctx)

    @commands.check(check_dj)
    @commands.command(name='leave', aliases=['l'])
    async def stop_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        try:
            check_music(ctx)
        except MusicChannelError as error:
            await error.do(ctx, self.client)
            return
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('Добавь музыку для флекса при помощи команды `.flex` :dancer:', delete_after=20)
        vc.pause()
        await ctx.message.delete()
        await ctx.send(f'`{ctx.message.author.name}` попросил{postix(ctx)} покинуть сервер :sleepy:', delete_after=20)
        try:
            player = self.players[ctx.guild.id]
            queue = self.queues[ctx.guild.id]
            self.queues[ctx.guild.id] = MusicQueue(player)
            await self.cleanup(ctx.guild)
            try:
                if player.queue.qsize() > 0:
                    track = await player.queue.get()
                    if track.src['id']:
                        try:
                            msg = await ctx.channel.fetch_message(track.src['id'])
                            await msg.delete()
                        except discord.HTTPException:
                            pass
                    for _ in range(len(queue)):
                        if isinstance(queue[0], YTDLSource):
                            track = (await queue.pop()).src
                            if track['id']:
                                try:
                                    msg = await ctx.channel.fetch_message(track['id'])
                                    await msg.delete()
                                except discord.HTTPException:
                                    pass
                        else:
                            track = await queue.pop()
                            if track['id']:
                                try:
                                    msg = await ctx.channel.fetch_message(track['id'])
                                    await msg.delete()
                                except discord.HTTPException:
                                    pass
            except IndexError:
                pass
            finally:
                player.dy = False
        except KeyError:
            pass
    @stop_.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f'Прости `{ctx.message.author.name}` но у тебя не прав ДиДжея :headphones:')
        else:
            await exp(ctx)

    @commands.command(name='history', aliases=['h'])
    async def history_(self, ctx, n):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        n = 1000 if n == 'all' else int(n)
        with open(f"{ctx.guild.id}/history.json", 'r') as f:
            d = json.load(f)
        h = d[::-1][:n]
        if n > len(h):
            n = len(h)
        await ctx.message.delete()
        if n <= 50:
            for i in range(0, n, 10):
                lh = h[i:i + 10]
                embed = discord.Embed(
                    colour=discord.Colour.blurple()
                )
                embed.add_field(name=f'История плейлиста [{i + 1}-{i + 10 if n > i + 10 else n}]',
                                value='\n'.join([f'{i + j + 1}. **{lh[j][0]}** '
                                                 f'`{self.client.get_user(lh[j][1]).name}`' for j in range(len(lh))]))
                await ctx.send(embed=embed, delete_after=3600)
        else:
            with open(f'{ctx.guild.id}tmp.html', 'w', encoding='utf-8') as f:
                f.write('<body style="background-color: #2f3136;color: #dcddde;">')
                f.write(f'<h2 style="color: #72767d">История плейлиста сервера {ctx.guild.name} [1-{n}]</h2>')
                f.write('<ol>')
                for i in range(n):
                    f.write(f'<li style="margin-bottom: 2px;"><b>{h[i][0]}</b> '
                            f'<span style="display: inline-block;background-color: #000;padding: 3px 2px;'
                            f'border-radius: 5px;">{self.client.get_user(h[i][1]).name}</code></li>')
                f.write('</ol></body>')
                f.close()
            await ctx.send(file=discord.File(f'{ctx.guild.id}tmp.html', filename='music.html'), delete_after=3600)

    @history_.error
    async def history_error(self, ctx, error):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        if isinstance(error, commands.errors.BadArgument):
            await ctx.send(f'`{ctx.message.content.replace(".m.h ", "")}` не является числом :wheelchair:',
                           delete_after=10)
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send('Надо указать кол-во интересующих записей :notepad_spiral:', delete_after=10)
        else:
            await exp(ctx)

    @commands.command(name='top', aliases=['m.top'])
    async def top_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        medals = [':first_place:', ':second_place:', ':third_place:']
        songs, users = Counter(), Counter()

        with open(f"{ctx.guild.id}/history.json", 'r') as f:
            d = json.load(f)

        for x in d:
            songs[x[0]] += 1
            users[x[1]] += 1
        songs, users = songs.most_common(3), users.most_common(3)

        songs = '\n'.join([f'{medals[i]} **{songs[i][0]}** '
                           f'`{str(songs[i][1]) + " раз" + wordend(songs[i][1], five="")}`'
                           for i in range(len(songs))])
        users = '\n'.join([f'{medals[i]} **{self.client.get_user(users[i][0]).name}** '
                           f'`{str(users[i][1]) + " запрос" + wordend(users[i][1])}`'
                           for i in range(len(users))])

        embed = discord.Embed(colour=int("FFD700", 16), title=f'Топ сервера `{ctx.guild.name}`')
        embed.add_field(name='Самые популярные песни', value=songs, inline=False)
        embed.add_field(name='Лидеры по количеству запросов', value=users, inline=True)
        embed.set_footer(text=f'Всего в истории сервера записано {len(d)} песен. '
                              f'Используй команду .h all чтобы посмотреть всю историю')

        await ctx.message.delete()
        await ctx.send(embed=embed, delete_after=3600)

    @commands.command(name='download', aliases=['d'])
    async def download_(self, ctx, *, query: str):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        await ctx.trigger_typing()
        if re.match(r'https://www.youtube.com/watch\?v=([a-zA-Z0-9\-]+)', query):
            fid = re.match(r'https://www.youtube.com/watch\?v=([a-zA-Z0-9\-]+)', query).groups()[0]
        else:
            sk = {}
            msg_logs = []
            while not sk:
                try:
                    async with timeout(5):
                        sk = yt_search(query, 'snippet', 1, 'video')
                except ConnectionResetError:
                    msg_log = await ctx.send('Проблемы с подключением к Youtube :link:\n'
                                             'Попытка создать новое соединение :wrench:')
                    msg_logs.append(msg_log)
                except asyncio.TimeoutError:
                    continue
            fid = sk.get("items", [])[0]["id"]["videoId"]

        res = yt_request('https://www.googleapis.com/youtube/v3/videos',
                         params={
                             'id': fid,
                             'part': 'snippet,contentDetails'
                         })
        t = re.findall(r'\d+', res.json()["items"][0]["contentDetails"]["duration"])
        dur, j = 0, 1
        for i in t[::-1]:
            dur += int(i) * j
            j *= 60
        if len(t) == 1:
            durs = f'0:{t[0] if len(t[0]) > 1 else "0" + t[0]}'
        else:
            for i in range(1, len(t)):
                if len(t[i]) != 2:
                    t[i] = '0' + t[i]
            durs = ':'.join(t)
        embed = discord.Embed(
            colour=discord.Colour(16711893),
            description=f'> [{res.json()["items"][0]["snippet"]["title"]}]'
            f'(https://www.youtube.com/watch?v={fid}) `[{durs}]`'
        )
        embed.set_author(name='Проверь ту ли композицию я нашла',
                         icon_url='https://cdn.discordapp.com/avatars/669163733473296395/'
                                  '89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        try:
            embed.set_thumbnail(url=res.json()["items"][0]["snippet"]["thumbnails"]["maxres"]["url"])
        except KeyError:
            try:
                embed.set_thumbnail(url=res.json()["items"][0]["snippet"]["thumbnails"]["standard"]["url"])
            except KeyError:
                try:
                    embed.set_thumbnail(url=res.json()["items"][0]["snippet"]["thumbnails"]["high"]["url"])
                except KeyError:
                    pass
        sms = await ctx.send(embed=embed)
        await sms.add_reaction('✅')
        await sms.add_reaction('❌')

        def check(reaction, user):
            return user == ctx.message.author

        try:
            reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=60)
            if str(reaction.emoji) == '✅':
                await sms.delete()
                await ctx.message.delete()

                if dur >= 599:
                    await ctx.send('Слишком долгая композиция для скачивания :weary:')
                    return
                msg = await ctx.send('Начинается загрузка...')
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192'
                    }]
                }
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={fid}'])

                for file in os.listdir("./"):
                    if fid in file:
                        await ctx.send(file=discord.File(file))
                        os.remove(file)
                await msg.delete()
            else:
                await sms.delete()
                await ctx.message.delete()
                await ctx.send(f'Жаль :pensive: Попробуй уточнить запрос :rolling_eyes:', delete_after=40)
        except asyncio.TimeoutError:
            await sms.delete()

    @commands.command(name='music_help', aliases=['m.help', 'm.h'])
    async def music_help(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(r=30, g=144, b=255),
            description=':headphones:`.dj` - в качестве аргумента передай либо **роль** и я устанавлю этой '
                        'роли права ДиДжея, либо **участника** сервера и я выдам ему роль ДиДжея при наличии таковой. '
                        '*При отсутствии* ***роли-диджея*** *на сервере мной может управлять любой его участник!* '
                        '**Нужны права администратора.**\n'
                        ':inbox_tray:`.j`,`.join` - устанавливаю соединение с голосовым каналом и присоединяюсь к '
                        'нему. *Тот, кто ввёл эту команду сам должен находиться в каком-либо голосовом канале.*\n'
                        ':notes:`.p`,`.play` - выполню поиск на *youtube* по строке или ссылке, переданной в '
                        'качестве аргумента и начну воспроизведение первого совпадения. **Нужны права Диджея.**\n'
                        ':mag_right:`.f`,`.find` - выполню поиск на *youtube* по строке и выдам 5 первых '
                        'совпадений. Автор должен указать любой из индексов этих результатов, чтобы я начала '
                        'играть найденный трек. **Нужны права Диджея.**\n'
                        ':track_next:`.s`,`.skip` - скип текущего трека. **Нужны права Диджея.**\n'
                        ':page_with_curl:`.pl`,`.playlist` - передай либо прямую ссылку на youtube-плейлист и я '
                        'начну его воспроизводить, или текст для поиска (алгоритм как для `.find`). Пропиши между '
                        'командой и строкой \'-r\' и треки в плейлисте перемешаются: `.pl -r best songs 2020`'
                        '**Нужны права Диджея.**\n'
                        ':fast_forward:`.ps`,`.playlist_skip` - скип целого плейлиста, который играет сейчас. '
                        '**Нужны права Диджея.**\n'
                        ':scroll:`.q`,`.queue` - покажу список треков, ожидающих воспроизведение в очереди.\n'
                        ':broom:`.qc`,`.queue_clean` - очищу всю очередь запросов\n'
                        ':notepad_spiral:`.t`,`.text` - попробую найти текст песни, которая воспроизводится в данный'
                        ' момент. *Пока поиску поддаются только весьма популярные треки*\n'
                        ':information_source:`.np`,`.now` - покажу трек, играющий в данный момент и сколько ещё '
                        'осталось времени до его завершения\n'
                        ':door:`.l`,`.leave` - останавлю музыкальное воспроизведение и покину голосовой канал, '
                        'очистив при этом очередь запросов. '
                        '*Я сделаю это автоматически, если в течение 10 минут не будет проигрываться музыка.* '
                        '**Нужны права Диджея.**\n'
        )
        embed.set_author(name='Музыкальные команды [часть 1]',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(r=30, g=144, b=255),
            description=':gear:`.m`,`.music` - текстовый канал, в котором ты вызовешь эту команду, я сделаю '
                        'музыкальным и все команды этого раздела будут выполняться только здесь. Чтобы отменить '
                        'настройку выполни команду `.m 0`\n'
                        ':clock4:`.h`,`.history` - показыжу последние запросы песен. В качестве аргумента '
                        'передай либо число *n* и тогда я покажу последние *n* произведений, либо параметр *all* и '
                        'тогда я показыжу всю историю сервера. Обрати внимание, что максимальное число записей '
                        '**1000**, т.к. более старые записи удаляются. *Если n > 99, то я пришлю html документ.*\n'
                        ':medal:`.top` - покажу самые популярные треки и самых популярных ДиДжеев сервера.\n'
                        ':arrow_down:`.d`,`.download` - передай в качестве аргумента строку или ссылку на *youtube* '
                        'видео и я пришлю в ответ аудио-файл, который можно скачать. *Длина трека до 10 минут!*'
        )
        embed.set_author(name='Музыкальные команды [часть 2]',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)

    @staticmethod
    def check_author(author):
        def inner_check(message):
            if message.author != author:
                return False
            if message.content.startswith(('.m.f', '.search', '.m.pl', '.playlist')):
                raise asyncio.TimeoutError
            try:
                return True if 1 <= int(message.content) <= 5 else False
            except ValueError:
                return False

        return inner_check


def setup(client):
    client.add_cog(Music(client))
