import discord
from discord.ext import commands
from cfg import discord_token, version

import os


pix = '.'
client = commands.Bot(command_prefix=pix)
client.remove_command('help')


async def default():
    await client.wait_until_ready()
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='.help'))


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        await ctx.message.delete()
        await ctx.send(f'Неизвестная команда `{ctx.message.content}` :thinking: '
                       f'Весь список команд: `.help`', delete_after=20)


@client.command()
async def logout():
    await client.logout()


@client.command(aliases=['help'])
async def help_(ctx):
    embed = discord.Embed(
        colour=discord.Colour.from_rgb(r=30, g=144, b=255),
        description='Ниже представлены списки команд каждого условного раздела. Чтобы подробнее узнать об их значении '
                    ' и о том, как можно писать их короче - обрати внимание на первую команду каждого списка :wink:. '
                    '*Команды одинакового значения распределены по блокам:*'
    )

    embed.set_author(name='Мои команды',
                     icon_url='https://cdn.discordapp.com/avatars/'
                              '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
    embed.add_field(name='Музыкальные команды [для некоторых нужны права ДиДжея]',
                    value='`.m.h` `.flex` `.find` `.playlist` `.playlist_skip` `.dj` `.join` `.skip` `.pause` '
                          '`.resume` `.stop` `.queue` `.queue_clean` `.text` `.now` `.history` `.top` `.download` '
                          '`.music`',
                    inline=False)
    embed.add_field(name='Серверные команды [для всех нужны права Администратора]',
                    value='`.s.h` `.set_roles` `.set_genders` `.channels` `.edit.notice` `.edit.now` `.edit.count`',
                    inline=False)
    embed.add_field(name='Персональные команды',
                    value='`.p.h` `.gender` `.avatar`',
                    inline=False)
    embed.add_field(name='Развлекательные команды',
                    value='`.e.h` `.random` `.upload`',
                    inline=False)
    embed.add_field(name='Дополнительные команды',
                    value='`.d.h` `.clear` `.bug` `.git`',
                    inline=False)
    embed.set_footer(text=f'версия {version}')
    await ctx.message.delete()
    await ctx.send(embed=embed)


for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')

client.loop.create_task(default())
client.run(discord_token)
