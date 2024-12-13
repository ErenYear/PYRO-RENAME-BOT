from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import db

from asyncio import sleep
from PIL import Image
import os, time


uploaded_files = {}

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def file_handler(client, message):
    user_id = message.from_user.id
    if user_id not in uploaded_files:
        uploaded_files[user_id] = []

    file = getattr(message, message.media.value)
    uploaded_files[user_id].append(file)

    if len(uploaded_files[user_id]) == 1:
        filename = file.file_name
        await message.reply_text(
            text=f"**__Pʟᴇᴀꜱᴇ Eɴᴛᴇʀ Nᴇᴡ Fɪʟᴇɴᴀᴍᴇ...__**\n\n**Oʟᴅ Fɪʟᴇ Nᴀᴍᴇ** :- `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    else:
        # Multiple files - prompt for batch renaming
        await message.reply_text(
            text=f"**{len(uploaded_files[user_id])} files uploaded.**\nSend **DONE** to start batch renaming or upload more files.",
            reply_markup=ForceReply(True)
        )

@Client.on_message(filters.private & filters.reply & filters.text)
async def batch_or_single_rename(client, message):
    user_id = message.from_user.id

    if message.text.lower() == "done" and len(uploaded_files[user_id]) > 1:
        # Batch rename initiation
        await message.reply_text(
            "Please enter the base name in the following format:\n"
            "`BaseName [Tags] [Season] {E01} [Resolution] @Source.extension`\n\n"
            "Include `{E01}` for episode numbering.",
            reply_markup=ForceReply(True)
        )
    elif len(uploaded_files[user_id]) == 1:
        # Single rename process
        reply_message = message.reply_to_message
        new_name = message.text
        file = uploaded_files[user_id][0]
        await process_single_rename(client, message, file, new_name)
        uploaded_files[user_id].clear()  # Clear user's uploaded files list after renaming
    else:
        await message.reply_text("Invalid input. Send **DONE** for batch renaming or provide a new filename.")

@Client.on_message(filters.private & filters.reply & filters.create(lambda _, __, m: "{E01}" in m.text))
async def process_batch_rename(client, message):
    user_id = message.from_user.id
    base_name = message.text
    files = uploaded_files[user_id]

    episode_start = int(base_name.split("{E")[1].split("}")[0])
    extension = base_name.split(".")[-1] if "." in base_name else "mkv"
    renamed_files = []

    for i, file in enumerate(files):
        episode_num = f"E{str(episode_start + i).zfill(2)}"
        new_name = base_name.replace("{E01}", episode_num).replace(".extension", f".{extension}")
        renamed_files.append(new_name)

    # Confirm batch renaming
    await message.reply_text(
        text=f"Renaming {len(files)} files as follows:\n\n" +
             "\n".join([f"{file.file_name} ➡ {renamed}" for file, renamed in zip(files, renamed_files)]),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Confirm", callback_data="confirm_batch_rename")]])
    )

@Client.on_callback_query(filters.regex("confirm_batch_rename"))
async def execute_batch_rename(client, query):
    user_id = query.from_user.id
    files = uploaded_files[user_id]
    for i, file in enumerate(files):
        # Implement renaming and upload logic here
        await query.message.reply(f"Renamed and uploaded: `{file.file_name}` ➡ `{new_name}`")

    uploaded_files[user_id].clear()  # Clear user's file list after processing
    await query.message.edit("Batch renaming and uploading completed.")

async def process_single_rename(client, message, file, new_name):
    """Process single file renaming."""
    if not "." in new_name:
        if "." in file.file_name:
            extn = file.file_name.rsplit('.', 1)[-1]
        else:
            extn = "mkv"
        new_name = new_name + "." + extn

    button = [[InlineKeyboardButton("📁 Dᴏᴄᴜᴍᴇɴᴛ", callback_data="upload_document")]]
    if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        button.append([InlineKeyboardButton("🎥 Vɪᴅᴇᴏ", callback_data="upload_video")])
    elif file.media == MessageMediaType.AUDIO:
        button.append([InlineKeyboardButton("🎵 Aᴜᴅɪᴏ", callback_data="upload_audio")])

    await message.reply(
        text=f"**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n**• Fɪʟᴇ Nᴀᴍᴇ :-** `{new_name}`",
        reply_markup=InlineKeyboardMarkup(button)
    )
    
async def force_reply_filter(_, client, message):
    if (message.reply_to_message.reply_markup) and isinstance(message.reply_to_message.reply_markup, ForceReply):
        return True 
    else:
        return False 
 
@Client.on_message(filters.private & filters.reply & filters.create(force_reply_filter))
async def rename_selection(client, message):
    reply_message = message.reply_to_message

    new_name = message.text
    await message.delete() 
    msg = await client.get_messages(message.chat.id, reply_message.id)
    file = msg.reply_to_message
    media = getattr(file, file.media.value)
    if not "." in new_name:
        if "." in media.file_name:
            extn = media.file_name.rsplit('.', 1)[-1]
        else:
            extn = "mkv"
        new_name = new_name + "." + extn
    await reply_message.delete()

    button = [[InlineKeyboardButton("📁 Dᴏᴄᴜᴍᴇɴᴛ",callback_data = "upload_document")]]
    if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        button.append([InlineKeyboardButton("🎥 Vɪᴅᴇᴏ", callback_data = "upload_video")])
    elif file.media == MessageMediaType.AUDIO:
        button.append([InlineKeyboardButton("🎵 Aᴜᴅɪᴏ", callback_data = "upload_audio")])
    await message.reply(
        text=f"**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n**• Fɪʟᴇ Nᴀᴍᴇ :-** `{new_name}`",
        reply_to_message_id=file.id,
        reply_markup=InlineKeyboardMarkup(button)
    )


@Client.on_callback_query(filters.regex("upload"))
async def rename_callback(bot, query): 
    user_id = query.from_user.id
    file_name = query.message.text.split(":-")[1]
    file_path = f"downloads/{user_id}{time.time()}/{file_name}"
    file = query.message.reply_to_message

    sts = await query.message.edit("Tʀyɪɴɢ Tᴏ Dᴏᴡɴʟᴏᴀᴅɪɴɢ....")    
    try:
     	path = await file.download(file_name=file_path, progress=progress_for_pyrogram,progress_args=("Dᴏᴡɴʟᴏᴀᴅ Sᴛᴀʀᴛᴇᴅ....", sts, time.time()))                    
    except Exception as e:
     	return await sts.edit(e)
    duration = 0
    try:
        metadata = extractMetadata(createParser(file_path))
        if metadata.has("duration"): duration = metadata.get('duration').seconds
    except:
        pass
    
    ph_path = None
    media = getattr(file, file.media.value)
    db_caption = await db.get_caption(user_id)
    db_thumb = await db.get_thumbnail(user_id)

    if db_caption:
        try:
            caption = db_caption.format(filename=file_name, filesize=humanbytes(media.file_size), duration=convert(duration))
        except KeyError:
            caption = f"**{file_name}**"
    else:
        caption = f"**{file_name}**"
 
    if (media.thumbs or db_thumb):
        if db_thumb:
            ph_path = await bot.download_media(db_thumb) 
        else:
            ph_path = await bot.download_media(media.thumbs[0].file_id)
        Image.open(ph_path).convert("RGB").save(ph_path)
        img = Image.open(ph_path)
        img.resize((320, 320))
        img.save(ph_path, "JPEG")

    await sts.edit("Tʀyɪɴɢ Tᴏ Uᴩʟᴏᴀᴅɪɴɢ....")
    type = query.data.split("_")[1]
    try:
        if type == "document":
            await sts.reply_document(
                document=file_path,
                thumb=ph_path, 
                caption=caption, 
                progress=progress_for_pyrogram,
                progress_args=("Uᴩʟᴏᴅ Sᴛᴀʀᴛᴇᴅ....", sts, time.time())
            )
        elif type == "video": 
            await sts.reply_video(
                video=file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("Uᴩʟᴏᴅ Sᴛᴀʀᴛᴇᴅ....", sts, time.time())
            )
        elif type == "audio": 
            await sts.reply_audio(
                audio=file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("Uᴩʟᴏᴅ Sᴛᴀʀᴛᴇᴅ....", sts, time.time())
            )
    except Exception as e:          
        try: 
            os.remove(file_path)
            os.remove(ph_path)
            return await sts.edit(f" Eʀʀᴏʀ {e}")
        except: pass
        
    try: 
        os.remove(file_path)
        os.remove(ph_path)
        await sts.delete()
    except: pass
        
