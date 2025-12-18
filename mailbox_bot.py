##MTQzNDIzMzU1MzY4MzQ4NDgwNg.GoZ8cB.K79Uh4BG8aWFO-8aEVW8G-XlTidEPyOcsm1N8I
import discord
from discord.ext import commands
from discord import app_commands
import random
import string
from PIL import Image
import io

# === CONFIG ===
TOKEN = "MTQzNDIzMzU1MzY4MzQ4NDgwNg.GoZ8cB.K79Uh4BG8aWFO-8aEVW8G-XlTidEPyOcsm1N8I"
ADMIN_ROLE_NAME = "The State"
CATEGORY_NAME = "Mailboxes"

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.guilds = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

# --- Helper functions ---
def generate_id(length=4):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

async def get_or_create_category(guild):
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)
    return category


async def attachment_to_grayscale_file(attachment: discord.Attachment) -> discord.File:
    image_bytes = await attachment.read()

    with Image.open(io.BytesIO(image_bytes)) as img:
        gray = img.convert("L")
        output = io.BytesIO()
        gray.save(output, format=img.format)
        output.seek(0)

    return discord.File(fp=output, filename=attachment.filename)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()


# --- Create mailbox ---
@bot.tree.command(name="mailbox_setup", description="Create inbox and outbox channels for a user.")
@app_commands.describe(user="User to create mail channels for")
async def mailbox_setup(interaction: discord.Interaction, user: discord.User):
    guild = interaction.guild
    admin_role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)

    if not admin_role:
        await interaction.response.send_message(
            f"No role named '{ADMIN_ROLE_NAME}' found.",
            ephemeral=True
        )
        return

    category = await get_or_create_category(guild)
    uid = generate_id()

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }

    inbox = await guild.create_text_channel(f"inbox-{uid}", overwrites=overwrites, category=category)
    outbox = await guild.create_text_channel(f"outbox-{uid}", overwrites=overwrites, category=category)

    await inbox.send(f"📬 Your inbox. Mailbox ID: `{uid}`")
    await outbox.send("✉️ Use `!telegram <mailbox_id> [message]` and attach files/images.")

    await interaction.response.send_message(
        f"Mailbox created for {user.mention} (`{uid}`)",
        ephemeral=True
    )


# --- Telegram sending (FIRST IMAGE IN MAIN EMBED) ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.channel.name.startswith("outbox-"):
        return

    if not message.content.startswith("!telegram"):
        return

    parts = message.content.split(" ", 2)
    if len(parts) < 2:
        await message.channel.send("Usage: `!telegram <mailbox_id> [message]`")
        return

    mailbox_id = parts[1].lower()
    body_text = parts[2] if len(parts) >= 3 else ""

    inbox = discord.utils.get(message.guild.channels, name=f"inbox-{mailbox_id}")
    if not inbox:
        await message.channel.send("Inbox not found.")
        return

    sender_code = message.channel.name.replace("outbox-", "")

    # Separate attachments
    image_attachments = []
    other_files = []

    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image"):
            image_attachments.append(attachment)
        else:
            other_files.append(attachment)

    # --- MAIN EMBED ---
    main_embed = discord.Embed(
        title="📨 New Telegram",
        description=body_text if body_text else "*No message body*",
        color=discord.Color.from_rgb(230, 230, 230)
    )
    main_embed.set_footer(text=f"Sent from mailbox ID: {sender_code}")

    files = []

    # Attach non-image files
    for attachment in other_files:
        files.append(await attachment.to_file())

    # FIRST IMAGE → MAIN EMBED
    remaining_images = image_attachments
    if image_attachments:
        first_image = image_attachments[0]
        gray_file = await attachment_to_grayscale_file(first_image)
        files.append(gray_file)
        main_embed.set_image(url=f"attachment://{first_image.filename}")
        remaining_images = image_attachments[1:]

    await inbox.send(embed=main_embed, files=files)

    # --- EXTRA IMAGE EMBEDS ---
    for index, attachment in enumerate(remaining_images, start=2):
        gray_file = await attachment_to_grayscale_file(attachment)

        image_embed = discord.Embed(
            title="🖼️ Attached Image",
            description=f"Attached image {index}",
            color=discord.Color.from_rgb(230, 230, 230)
        )
        image_embed.set_image(url=f"attachment://{attachment.filename}")

        await inbox.send(embed=image_embed, files=[gray_file])

    await message.channel.send(f"Message sent to mailbox `{mailbox_id}`.")

    await bot.process_commands(message)


# --- Admin clear ---
@bot.tree.command(name="mailbox_clear", description="Delete all mailbox channels.")
async def mailbox_clear(interaction: discord.Interaction):
    guild = interaction.guild
    admin_role = discord.utils.get(guild.roles, name=ADMIN_ROLE_NAME)

    if admin_role not in interaction.user.roles:
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        await interaction.response.send_message("No mailboxes found.", ephemeral=True)
        return

    for channel in category.channels:
        await channel.delete()
    await category.delete()

    await interaction.response.send_message("Mailboxes deleted.", ephemeral=True)


bot.run(TOKEN)
