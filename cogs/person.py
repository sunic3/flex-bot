import traceback

import discord
from discord.ext import commands

from cogs.bot import channel_check, ChannelException
from bottools import data_read, data_write


class Person(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = self.client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        member = discord.utils.get(message.guild.members, id=payload.user_id)
        try:
            if member.id != 669163733473296395:
                d = data_read(message.guild)
                if int(d["autoroles_post_id"].split(',')[1]) == payload.message_id:
                    try:
                        role = discord.utils.get(message.guild.roles, id=d["autoroles"][str(payload.emoji)])
                        await member.add_roles(role)
                    except KeyError:
                        await message.remove_reaction(payload.emoji, member)
                        return
        except discord.Forbidden:
            await channel.send('У бота недостаточно прав. Попробуй в настройках сервера '
                               'расположить роль бота как можно выше :pleading_face:', delete_after=40)
        except Exception:
            traceback.print_exc()
            await channel.send('Неизвестная ошибка :eyes:', delete_after=20)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        channel = self.client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        member = discord.utils.get(message.guild.members, id=payload.user_id)
        if member is not None:
            try:
                if member.id != 669163733473296395:
                    d = data_read(message.guild)
                    if int(d["autoroles_post_id"].split(',')[1]) == payload.message_id:
                        try:
                            role = discord.utils.get(message.guild.roles, id=d["autoroles"][str(payload.emoji)])
                            await member.remove_roles(role)
                        except KeyError:
                            return
            except discord.Forbidden:
                await channel.send('У бота недостаточно прав. Попробуй в настройках сервера '
                                   'расположить роль бота как можно выше :pleading_face:', delete_after=40)
            except Exception:
                await channel.send('Неизвестная ошибка :eyes:', delete_after=20)

    @commands.command(aliases=['g'])
    async def change_gender(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        user = ctx.message.author
        d = data_read(ctx.guild)
        if d['genders']:
            role1 = discord.utils.get(user.guild.roles, id=d['genders'][0])
            role2 = discord.utils.get(user.guild.roles, id=d['genders'][1])
            if role1 is None or role2 is None:
                await ctx.message.delete()
                await ctx.send(f'Упс! Кажется кто-то из админов сервера удалил роли. Попроси '
                               f'`{ctx.guild.owner.name}` поставить их заново :cowboy:', delete_after=40)
            if role1.name in [r.name for r in user.roles]:
                await user.remove_roles(role1)
                await user.add_roles(role2)
            else:
                await user.remove_roles(role2)
                await user.add_roles(role1)
            await ctx.message.delete()
            await ctx.send(f'{user.mention}, ты изменил свою гендерную роль :sunglasses:', delete_after=3)
        else:
            ctx.send('К сожалению, владелец сервера не назначили роли для гендерного распределения :weary:')

    @commands.command(name='avatar', aliases=['ava'])
    async def get_avatar(self, ctx, *members: discord.Member):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        await ctx.message.delete()
        if not members:
            members = [ctx.message.author]
        for member in members:
            embed = discord.Embed(
                color=member.color
            )
            embed.set_image(url=member.avatar_url)
            await ctx.send(embed=embed)

    @commands.command(name='person_help', aliases=['p.h'])
    async def person_help_(self, ctx):
        try:
            channel_check(ctx)
        except ChannelException as error:
            await error.do(ctx)
            return
        await ctx.message.delete()
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(r=30, g=144, b=255),
            description=':cat:`.g`,`.change_gender` - если пол, который я выдала тебе автоматически, тебя не '
                        'устраивает, ты можешь его сам поменять.\n'
                        ':stars:`.ava` - пришлю фотку твоей аватарки, или аватарки любого другого участника сервера, '
                        'главное не забудь отметить его в сообщении'
        )
        embed.set_author(name='Персональные команды',
                         icon_url='https://cdn.discordapp.com/avatars/'
                                  '669163733473296395/89d3cf65e539aaba9e6d1669d32b1ea7.webp?size=1024')
        await ctx.send(embed=embed, delete_after=3600)

    @commands.command(name='notice')
    async def notice_(self, ctx):
        d = data_read(ctx.guild)
        if ctx.message.author.id in d['notices']:
            d['notices'].remove(ctx.message.author.id)
        else:
            d['notices'].append(ctx.message.author.id)
        data_write(ctx.guild, d)
        await ctx.send(f'`{ctx.message.author.name}` всё :ok:')


def setup(client):
    client.add_cog(Person(client))
