from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, humanbytes
from helper.database import db
from asyncio import sleep
from PIL import Image
import os, time

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_handler(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name  
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sᴏʀʀy, ᴛʜɪꜱ ʙᴏᴛ ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ꜰɪʟᴇꜱ ʟᴀʀɢᴇʀ ᴛʜᴀɴ 2Gʙ.")

    try:
        await message.reply_text(
            text=f"**__Enter a new file name.__**\n\n**Old File Name:** `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except FloodWait as e:
        await sleep(e.value)
        await rename_handler(client, message)
    except:
        pass

async def force_reply_filter(_, client, message):
    return (message.reply_to_message.reply_markup) and isinstance(message.reply_to_message.reply_markup, ForceReply)

@Client.on_message(filters.private & filters.reply & filters.create(force_reply_filter))
async def rename_and_upload(client, message):
    reply_message = message.reply_to_message
    new_name = message.text
    await message.delete() 

    original_message = await client.get_messages(message.chat.id, reply_message.id)
    file = original_message.reply_to_message
    media = getattr(file, file.media.value)

    if not "." in new_name:
        extn = media.file_name.rsplit('.', 1)[-1] if "." in media.file_name else "mkv"
        new_name = f"{new_name}.{extn}"

    file_path = f"downloads/{file.chat.id}/{time.time()}/{new_name}"
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        status_message = await reply_message.reply("**Downloading...**")
        path = await file.download(file_path, progress=progress_for_pyrogram, progress_args=("**Downloading...**", status_message, time.time()))
    except Exception as e:
        return await status_message.edit(f"**Download failed:** {e}")

    duration = 0
    try:
        metadata = extractMetadata(createParser(path))
        if metadata and metadata.has("duration"):
            duration = metadata.get("duration").seconds
    except:
        pass

    thumbnail_path = None
    if media.thumbs:
        thumbnail_path = await client.download_media(media.thumbs[0].file_id)
        Image.open(thumbnail_path).convert("RGB").save(thumbnail_path)

    user_caption = await db.get_caption(message.chat.id)
    caption = user_caption.format(filename=new_name, filesize=humanbytes(media.file_size), duration=duration) if user_caption else f"**{new_name}**"

    await status_message.edit("**Uploading...**")
    try:
        await reply_message.reply_document(
            document=path,
            caption=caption,
            thumb=thumbnail_path
        )
        await status_message.delete()
    except Exception as e:
        await status_message.edit(f"**Upload failed:** {e}")

    try:
        os.remove(path)
        if thumbnail_path:
            os.remove(thumbnail_path)
    except:
        pass
        
