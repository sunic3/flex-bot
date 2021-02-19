import discord
from discord.ext import commands
from discord.ext.commands import has_permissions, errors

from bottools import wordend, data_read, data_write, exp, postix
from cogs.bot import channel_check, ChannelException
from cfg import version

import traceback
import asyncio
import typing
import json
import os


class Serv(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.members = {}
        self.banned = {}

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        info = discord.utils.find(lambda x: x.permissions_for(guild.me).send_messages, guild.text_channels)
        owner = await guild.fetch_member(guild.owner_id)
        embed = discord.Embed(colour=discord.Colour.green(), title=f'Приветик, {guild.name}:heart_exclamation:',
                              description=f'Спасибочки за приглашение на свой сервер, {owner.mention} '
                                          f':revolving_hearts:\nВ основном, я выполняю функции музыкального бота. '
                                          f'Напиши `.m.h` чтобы посмотреть их. Рекомендую выбрать специальный канал '
                                          f'для музыки и прописать там `.music`.\nЕсли тебе интересно поподробнее '
                                          f'узнать о других моих возможностях, напиши `.help`'
                              )
        embed.set_image(url='https://i.ibb.co/QmfMN1b/image.gif')
        embed.set_footer(text=f'версия {version}')
        await info.send(embed=embed)
        os.mkdir(f'{guild.id}')
        d = {'autoroles': {}, 'autoroles_post_id': None, 'genders': [], 'dj': None, 'notices': [],
             'music_id': None, 'channels': [], 'current': None, 'now': True, 'notice': True, 'count': 5}
        data_write(guild, d)
        with open(f"{guild.id}/history.json", "w") as f:
            json.dump([], f)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await asyncio.sleep(15)
        dir_name = f'{guild.id}'
        for file in os.listdir(dir_name):
            file_path = os.path.join(dir_name, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir(dir_name)
        print(f'successfully deleted {guild.id} directory')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot:
            d = data_read(member.guild)
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(r=43, g=181, b=81),
                description=f'{member.mention} добро пожаловать на сервер **'
                            f'{member.guild.name}**:heart_exclamation:\n\n'
            )
            embed.set_thumbnail(url=member.guild.icon_url)
            embed.set_author(name='новый участник сервера', icon_url=member.avatar_url)
            if d['autoroles_post_id']:
                msg = await discord.utils.get(member.guild.text_channels,
                                              id=int(d['autoroles_post_id'].split(',')[0]))\
                    .fetch_message(int(d['autoroles_post_id'].split(',')[1]))
                if msg:
                    embed.description += f'Обрати внимание на [этот пост]({msg.jump_url})' \
                        f'. Здесь ты можешь выбрать все интересующие тебя роли.:love_you_gesture:\n\n'
            if d['genders']:
                role = discord.utils.get(member.guild.roles, id=d['genders'][0])
                await member.add_roles(role)
                embed.description += f'По умолчанию тебе добавлена гендерная роль `{role.name}` :male_sign:. ' \
                    f'Если хочешь изменить её - пропиши команду `.g`'
            embed.set_footer(text='Все мои команды ты можешь подсмотреть с помощью `.help`')
            if d['channels']:
                info = discord.utils.get(member.guild.text_channels, id=d['channels'][0])
            else:
                info = discord.utils.find(lambda x: x.permissions_for(member.guild.me).send_messages,
                                          member.guild.text_channels)
            await info.send(f'{member.mention}', delete_after=1)
            await info.send(embed=embed, delete_after=120)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not member.bot:
            d = data_read(member.guild)
            if d['autoroles_post_id']:
                msg = await discord.utils.get(member.guild.text_channels,
                                              id=int(d['autoroles_post_id'].split(',')[0])) \
                    .fetch_message(int(d['autoroles_post_id'].split(',')[1]))
                for e in d['autoroles'].keys():
                    try:
                        await msg.remove_reaction(e, member)
                    except Exception:
                        continue

    @commands.command()
    @commands.check(channel_check)
    @has_permissions(administrator=True)
    async def set_genders(self, ctx, *roles: typing.Union[discord.Role, str]):
        s = ctx.message.author.guild
        if len(roles) == 0:
            r1 = await s.create_role(name='♂', colour=discord.Colour.blue(), mentionable=True)
            r2 = await s.create_role(name='♀', colour=discord.Colour(16711893), mentionable=True)
        elif len(roles) == 2:
            if isinstance(roles[0], discord.Role):
                r1 = roles[0]
                r2 = roles[1]
            else:
                r1 = await s.create_role(name=roles[0], colour=discord.Colour.blue(), mentionable=True)
                r2 = await s.create_role(name=roles[1], colour=discord.Colour(16711893), mentionable=True)
        else:
            raise errors.BadArgument
        d = data_read(ctx.guild)
        d['genders'] = [r1.id, r2.id]
        data_write(ctx.guild, d)
        await ctx.message.delete()
        await ctx.send(f'" роли[`{r1.name}` и `{r2.name}`] успешно установлены как гендерные :male_sign: :female_sign:',
                       delete_after=40)

    @set_genders.error
    async def set_genders_error(self, ctx, error):
        await ctx.message.delete()
        if isinstance(error, errors.BadArgument):
            await ctx.send('Указано неверное количество ролей или данные введены некорректно :monkey:', delete_after=40)
        elif isinstance(error, errors.MissingPermissions):
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=40)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        else:
            await exp(ctx)

    @commands.command(name='set_roles')
    @has_permissions(administrator=True)
    async def set_roles_(self, ctx, *role: typing.Union[discord.Role, str]):
        if len(role) == 0:
            return await ctx.send(f'Ты забыл{postix(ctx)} указать роли')
        try:
            embed = discord.Embed(
                title="Раздача ролей",
                description='',
                colour=discord.Colour.green()
            )
            if isinstance(role[0], str):
                if role[0] != '-i':
                    embed.description = role[0]+'\n\n'
                    if len(role) > 1 and isinstance(role[1], str) and role[1] == '-i':
                        pass
                    else:
                        embed.set_thumbnail(url=ctx.guild.icon_url)
                else:
                    embed.set_thumbnail(url=ctx.guild.icon_url)
            embed.set_footer(text='Нажмите на соответствующий Эмодзи, чтобы получить роль\n')

            text, reacts = '', {}
            for i in range(len(role)):
                r = role[i]
                t = []
                if isinstance(r, discord.Role):
                    t.append(r)
                    if i < len(role)-1 and isinstance(role[i+1], str):
                        t.append(role[i+1])
                        i += 1
                        if i < len(role)-1 and isinstance(role[i+1], str):
                            t.append(f' --- {role[i+1]}')
                            i += 1
                        else:
                            t.append("")
                    else:
                        raise commands.errors.BadArgument
                    text += f'{t[1]} : {t[0].mention}{t[2]}\n\n'
                    reacts[t[1]] = t[0].id
            embed.description += text
            d = data_read(ctx.guild)
            if not d['autoroles_post_id']:
                sms = await ctx.send(embed=embed)
                await sms.pin()
                d['autoroles'] = reacts
                d['autoroles_post_id'] = f'{ctx.channel.id},{sms.id}'
                data_write(ctx.guild, d)
                for e in reacts:
                    await sms.add_reaction(e)
                await ctx.message.delete()
            else:
                new_sms = await ctx.send(f'Пост для выдачи авторолей уже сущесвует :pushpin:\nСоздать новый?')
                await new_sms.add_reaction('🆕')
                await new_sms.add_reaction('🚫')

                def check(reaction, user):
                    return user == ctx.message.author
                try:
                    reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=60)
                    if str(reaction.emoji) == '🆕':
                        if len(reacts) > 20:
                            await ctx.send('Не удалось создать пост, т.к. невозможно добавить более 20 реакций на '
                                           'сообщение :no_entry:', delete_after=40)
                            return
                        try:
                            msg_d = await discord.utils.get(ctx.guild.text_channels,
                                                            id=int(d['autoroles_post_id'].split(',')[0]))\
                                .fetch_message(int(d['autoroles_post_id'].split(',')[1]))
                            await msg_d.delete()
                        except discord.HTTPException:
                            pass
                        except AttributeError:
                            pass
                        d = data_read(ctx.guild)
                        sms = await ctx.send(embed=embed)
                        await sms.pin()
                        d['autoroles'] = reacts
                        d['autoroles_post_id'] = f'{ctx.channel.id},{sms.id}'
                        data_write(ctx.guild, d)
                        for e in reacts:
                            await sms.add_reaction(e)
                        await ctx.message.delete()
                    await new_sms.delete()
                except asyncio.TimeoutError:
                    await new_sms.delete()
        except IndexError:
            await ctx.send("Аргументы переданы неверно :jack_o_lantern:", delete_after=40)
        except discord.HTTPException as e:
            if e.text == 'Unknown Emoji':
                await ctx.send("Дискорд не смог распознать некоторые Эмодзи :anguished:\nПопробуй ещё раз",
                               delete_after=30)
            else:
                pass
        except commands.errors.BadArgument:
            await ctx.send("Данные введены неправильно, проверь ещё раз :writing_hand:", delete_after=20)
        except Exception:
            await exp(ctx)
        finally:
            try:
                await asyncio.sleep(10)
                await ctx.message.delete()
            except discord.HTTPException:
                pass

    @commands.command(name='channels', aliases=['s.c'])
    @has_permissions(administrator=True)
    async def channels_(self, ctx, *chans: discord.TextChannel):
        await ctx.message.delete()
        if not chans:
            d = data_read(ctx.guild)
            d['channels'] = []
            data_write(ctx.guild, d)
            await ctx.send('Теперь можно писать команды в любом чате :hugging:', delete_after=20)
            return
        d = data_read(ctx.guild)
        d['channels'] = [chan.id for chan in chans]
        data_write(ctx.guild, d)
        await ctx.send(f'Эт{wordend(len(chans), "от", "и", "и")} {len(chans)} канал{wordend(len(chans), "", "а", "ов")}'
                       f' успешно установлен{wordend(len(chans), "", "ы", "ы")} как разрешённые :thumbsup::thumbsup:',
                       delete_after=40)

    @channels_.error
    async def channels_error(self, ctx, error):
        if isinstance(error, errors.BadArgument):
            await ctx.send('Указано неверное количество ролей или данные введены некорректно :monkey:', delete_after=40)
        elif isinstance(error, errors.MissingPermissions):
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=40)
        else:
            await ctx.send('Неизвестная ошибка :eyes:', delete_after=40)

    @commands.command(name='edit.notice')
    @has_permissions(administrator=True)
    async def notice_(self, ctx):
        channel_check(ctx)
        await ctx.message.delete()
        d = data_read(ctx.guild)
        d['notice'] = not d['notice']
        data_write(ctx.guild, d)
        await ctx.send(f'Настройка `участник покинул канал` изменена на  [ {int(d["notice"])} ]  :thumbsup:',
                       delete_after=20)

    @notice_.error
    async def notice_error(self, ctx, error):
        if isinstance(error, errors.MissingPermissions):
            await ctx.message.delete()
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=10)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        else:
            traceback.print_exc()
            await ctx.send('Неизвестная ошибка :eyes:', delete_after=10)

    @commands.command(name='edit.now')
    @has_permissions(administrator=True)
    async def now_(self, ctx):
        channel_check(ctx)
        await ctx.message.delete()
        d = data_read(ctx.guild)
        d['now'] = not d['now']
        data_write(ctx.guild, d)
        await ctx.send(f'Настройка `сейчас играет` изменена на  [ {int(d["now"])} ]  :thumbsup:', delete_after=20)

    @now_.error
    async def now_error(self, ctx, error):
        if isinstance(error, errors.MissingPermissions):
            await ctx.message.delete()
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=10)
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        else:
            traceback.print_exc()
            await ctx.send('Неизвестная ошибка :eyes:')

    @commands.command(name='edit.count')
    @has_permissions(administrator=True)
    async def count_(self, ctx, *, n: int):
        channel_check(ctx)
        await ctx.message.delete()
        d = data_read(ctx.guild)
        if n < 5 or n > 10:
            raise commands.errors.BadArgument
        d['count'] = n
        data_write(ctx.guild, d)
        await ctx.send(f'Настройка `количество записей` изменена на  [ {n} ]  :thumbsup:', delete_after=20)

    @count_.error
    async def count_error(self, ctx, error):
        if isinstance(error, errors.MissingPermissions):
            await ctx.message.delete()
            await ctx.send('У тебя не достаточно прав :baby:', delete_after=10)
        elif isinstance(error, commands.errors.BadArgument):
            await ctx.send(f'{ctx.message.content.replace(".edit.count ", "")} не является числом между 5 и 10')
        elif isinstance(error, ChannelException):
            await error.do(ctx)
        else:
            await exp(ctx)

    @commands.command(name='server_help', aliases=['s.h'])
    async def server_help_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(r=30, g=144, b=255),
            description=':fox:`.set_roles` - создам закрепленный пост, с помощью которого участники сервера '
                        'смогут сами выбирать себе роли всего по клику на Эмодзи. Для этого содержимое сообщения должно'
                        ' быть такого вида: `.set_roles @<упоминание роли> <любое Эмодзи> \"<Описание>\"`. Описание '
                        'роли по желанию, количество ролей неограничено. *Убедись в настройках сервера что моя роль* '
                        '*расположена выше всех ролей в сообщении, таковы требования Дискорда.*\n'
                        ':male_sign:`.set_genders` - устанавлю связь между половыми ролями и участниками '
                        'сервера. В качестве аргумента передай либо упоминания 2-х ролей при условии что моя роль выше '
                        'их обоих, либо 2 слова, которые запустят процесс создания новых ролей с соответствующими им '
                        'наименованиям. Можешь вообще не передавать ничего и тогда новые роли будут выглядеть так: '
                        '♂ и ♀. *Порядок аргументов всегда такой: сначала для мужской роли, затем для женской*\n'
                        ':shield:`.channels` - определю для себя на каких текстовых каналах я могу вести '
                        'работу, а на каких нет. Для этого передай через пробел список разрешённых каналов (с помощью '
                        '\'#\'), либо не передавай ничего, и тогда список запрещённых для меня каналов станет пустым.\n'
                        ':arrows_counterclockwise:`.edit.notice` - по умолчанию, когда участник сервера покидает '
                        'голосовой канал - я присылаю уведомление о времени его пребывания на данном канале. Эту опцию '
                        'можно менять сколько угодно раз с помощью этой команды.\n'
                        ':arrows_counterclockwise:`.edit.now` - по умолчанию, когда начинает играть новая песня - я '
                        'пишу название этой песни. Эту опцию можно менять сколько угодно раз с помощью этой команды.\n'
                        ':five:`.edit.count` - по умолчанию, после поиска музыки показываются лишь первые 5 совпадений.'
                        ' Ты можешь изменить это количество на любое число от 5 до 10 включительно.'
        )
        embed.set_author(name='Серверные команды',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)


def setup(client):
    client.add_cog(Serv(client))
