import discord
from discord.ext import commands
from discord.ext.commands import has_permissions, errors

from bottools import data_read


class ChannelException(commands.CommandError):
    async def do(self, ctx):
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(f'Этот канал не предназеначен для общения со мной :frowning2:', delete_after=5)


def channel_check(ctx):
    d = data_read(ctx.guild)['channels']
    if d and ctx.channel.id not in d:
        raise ChannelException
    return True


class Bot(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command(aliases=['b.addrole'])
    @has_permissions(administrator=True)
    async def b_add_role(self, ctx, role: discord.Role):
        user = await ctx.message.author.guild.fetch_member(669163733473296395)
        user.add_roles(role)
        await ctx.message.delete()
        await ctx.send(f'Роль {role.name} успешно присвоена. Спасибо ^3')

    @commands.command(aliases=['b.rmrole'])
    @has_permissions(administrator=True)
    async def b_rm_role(self, ctx, role: discord.Role):
        user = await ctx.message.author.guild.fetch_member(669163733473296395)
        user.remove_roles(role)
        await ctx.message.delete()
        await ctx.send(f'Роль {role.name} удалена.')

    @b_add_role.error
    async def b_add_role_error(self, ctx, error):
        if isinstance(error, errors.BadArgument):
            await ctx.send('Такой роли не существует')
        elif isinstance(error, errors.MissingPermissions):
            await ctx.send('У тебя не достаточно прав')
        else:
            await ctx.send('Неизвестная ошибка')


def setup(client):
    client.add_cog(Bot(client))
