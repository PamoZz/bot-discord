# === main.py ===
import discord
from discord.ext import commands
from discord.ui import View, Select
import asyncio
import os
import re
import json
from threading import Thread
from flask import Flask

print("Script démarré")

# Récupération du token via variable d'environnement (Render)
TOKEN = os.environ.get("TOKEN")
print(f"TOKEN trouvé ? {'Oui' if TOKEN else 'Non'}")
if not TOKEN:
    print("ERREUR : Token non défini. Le bot va quitter.")
    exit(1)

# === Flask pour keep alive sur Render ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True  # Pour que Flask ne bloque pas la fermeture du programme
    t.start()

keep_alive()  # Démarre le serveur web en parallèle

# === CONFIGURATION ===
GUILD_ID = 1392420965077618759

# === IDs (attention, bien en int !) ===
LOG_BAN_ID = 1394098502455394345
LOG_CLEAR_ID = 1394098554854838402
WELCOME_CHANNEL_ID = 1392420965077618762
LEAVE_CHANNEL_ID = 1392420965077618763
LOG_ANTILINK_ID = 1394098632885797014
LOG_TICKET_ID = 1394098679278993528
TICKET_MESSAGE_CHANNEL_ID = 1392490677736313003
ROLE_MEMBRE_ID = 1392639695342665780
ROLE_NON_VERIFIE_ID = 1394098750230677514
STAFF_ROLE_ID = 1394098940068102244
TICKET_CATEGORY_NAME = "Support"
reaction_message_id = None

# === INTENTS ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="+", intents=intents)

violations = {}
blacklist = set()
URL_REGEX = re.compile(r"(https?://|www\.|discord\.gg/)", re.IGNORECASE)

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    print(f"✅ Connecté en tant que {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    if not message.author.guild_permissions.administrator and URL_REGEX.search(message.content):
        await message.delete()
        user_id = message.author.id
        violations[user_id] = violations.get(user_id, 0) + 1
        log_channel = bot.get_channel(LOG_ANTILINK_ID)
        if violations[user_id] == 1:
            try:
                await message.author.send("Tu as posté un lien interdit.")
            except Exception:
                pass
            await message.guild.kick(message.author)
        else:
            await message.guild.ban(message.author)
        if log_channel:
            await log_channel.send(f"{message.author} a été sanctionné.")
    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def setreactionrole(ctx):
    global reaction_message_id
    embed = discord.Embed(title="Vérification", description="Clique sur ✅ pour accéder au serveur.")
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    reaction_message_id = msg.id

@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id != reaction_message_id or str(payload.emoji) != "✅":
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member:
        return
    role = guild.get_role(ROLE_MEMBRE_ID)
    non_verifie = guild.get_role(ROLE_NON_VERIFIE_ID)
    if role:
        await member.add_roles(role)
    if non_verifie and non_verifie in member.roles:
        await member.remove_roles(non_verifie)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: int):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role:
        role = await ctx.guild.create_role(name="Muted")
        for ch in ctx.guild.channels:
            await ch.set_permissions(role, send_messages=False)
    await member.add_roles(role)
    await ctx.send(f"{member} est mute pour {duration} minute(s).")
    await asyncio.sleep(duration * 60)
    await member.remove_roles(role)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"{member} est unmute.")
    else:
        await ctx.send(f"{member} n'est pas mute.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 {amount} messages supprimés.", delete_after=3)

@bot.command()
@commands.has_permissions(administrator=True)
async def clear_all(ctx):
    await ctx.channel.purge()
    await ctx.send("🧹 Tous les messages supprimés.", delete_after=3)

class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="buy", description="Acheter un produit"),
            discord.SelectOption(label="partenariat", description="Proposer un partenariat"),
            discord.SelectOption(label="support", description="Obtenir du support")
        ]
        super().__init__(placeholder="Choisissez une option", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(read_messages=True)
        }
        channel = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites, category=category)
        await interaction.response.send_message(f"Ticket créé: {channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.command()
@commands.has_permissions(administrator=True)
async def ticket(ctx):
    await ctx.send("🎟️ Crée un ticket :", view=TicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def backup_create(ctx):
    data = {
        "roles": [{"name": r.name, "permissions": r.permissions.value, "color": r.color.value} for r in ctx.guild.roles if not r.is_default()],
        "channels": [{"name": c.name, "type": str(c.type), "category": c.category.name if c.category else None} for c in ctx.guild.channels]
    }
    with open("backup.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    await ctx.send("📦 Backup créée.")

@bot.command()
@commands.has_permissions(administrator=True)
async def backup_put(ctx):
    with open("backup.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except Exception:
            pass
    for role in ctx.guild.roles:
        if not role.is_default():
            try:
                await role.delete()
            except Exception:
                pass
    for r in data["roles"]:
        await ctx.guild.create_role(name=r["name"], permissions=discord.Permissions(r["permissions"]), color=discord.Color(r["color"]))
    for c in data["channels"]:
        await ctx.guild.create_text_channel(name=c["name"])
    await ctx.send("📥 Backup restaurée.")

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"Erreur lors du lancement du bot : {e}")
    exit(1)
