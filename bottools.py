import discord

from cfg import youtube_token as yt

import traceback
import requests
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


TOKEN = yt[0]


def yt_next():
    global TOKEN
    if yt.index(TOKEN) == len(TOKEN)-1:
        TOKEN = yt[0]
    else:
        TOKEN = yt[yt.index(TOKEN)+1]


def postix(ctx):
    if isinstance(ctx, discord.Member):
        member = ctx
    else:
        member = ctx.message.author
    with open(f"{ctx.guild.id}/data.json", 'r') as f:
        d = json.load(f)['genders']
    if d:
        role1 = discord.utils.get(ctx.guild.roles, id=d[0])
        role2 = discord.utils.get(ctx.guild.roles, id=d[1])
        if role1 is None or role2 is None:
            return '(a)'
        postix = '' if role1.name in [y.name for y in member.roles] \
            else 'a' if role2.name in [y.name for y in member.roles] else '(a)'
        return postix
    else:
        return '(а)'


def wordend(d, one='', two='а', five='ов'):
    d = abs(d)
    if d == 1 or d > 20 and str(d)[-1] == '1' and str(d)[-2:] != '11':
        return one
    if 2 <= d <= 4 or d > 20 and str(d)[-1] in '234':
        return two
    return five


def data_read(guild):
    with open(f'{guild.id}/data.json', 'r') as f:
        data = json.load(f)
    return data


def data_write(guild, data):
    with open(f'{guild.id}/data.json', 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)


def yt_search(q, part, max, type):
    while True:
        try:
            sk = build("youtube", "v3", developerKey=TOKEN) \
                .search().list(q=q, part=part, maxResults=max, type=type).execute()
            return sk
        except KeyError:
            yt_next()
        except HttpError:
            yt_next()


def yt_playlist(part, id):
    while True:
        try:
            sk = build("youtube", "v3", developerKey=TOKEN) \
                .playlists().list(part=part, id=id).execute()
            return sk
        except KeyError:
            yt_next()
        except HttpError:
            yt_next()


def yt_request(url, params):
    params['key'] = TOKEN
    while True:
        try:
            res = requests.get(url, params=params)
            return res
        except KeyError:
            yt_next()
        except HttpError:
            yt_next()


def channels_perms(guild):
    d = data_read(guild)['channels']
    return d[0] if d else guild.text_channels[0].id


async def exp(ctx):
    traceback.print_exc()
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    await ctx.send('Неизвестная ошибка :eyes:')


async def mcm(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    except Exception:
        await exp(ctx)
