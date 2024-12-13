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


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_handler(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name  
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sᴏʀʀy Bʀᴏ Tʜɪꜱ Bᴏᴛ Iꜱ Dᴏᴇꜱɴ'ᴛ Sᴜᴩᴩᴏʀᴛ Uᴩʟᴏᴀᴅɪɴɢ Fɪʟᴇꜱ Bɪɢɢᴇʀ Tʜᴀɴ 2Gʙ")

    try:
        await message.reply_text(
            text=f"**__Pʟᴇᴀꜱᴇ Eɴᴛᴇʀ Nᴇᴡ Fɪʟᴇɴᴀᴍᴇ...__**\n\n**Oʟᴅ Fɪʟᴇ Nᴀᴍᴇ** :- `{filename}`",
    	    reply_to_message_id=message.id,  
    	    reply_markup=ForceReply(True)
        )       
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**__Pʟᴇᴀꜱᴇ Eɴᴛᴇʀ Nᴇᴡ Fɪʟᴇɴᴀᴍᴇ...__**\n\n**Oʟᴅ Fɪʟᴇ Nᴀᴍᴇ** :- `{filename}`",
    	    reply_to_message_id=message.id,  
    	    reply_markup=ForceReply(True)
        )
    except:
        pass


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


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def batch_rename_handler(client, message):
    if not hasattr(client, "file_batch"):
        client.file_batch = []
    
    file = getattr(message, message.media.value)
    client.file_batch.append((file, message))
    
    await message.reply_text(
        f"File `{file.file_name}` added to batch. Send more files or type **`/done`** to proceed with renaming."
    )

@Client.on_message(filters.private & filters.command("done"))
async def rename_batch_start(client, message):
    if not hasattr(client, "file_batch") or not client.file_batch:
        return await message.reply_text("No files in the batch. Add files first.")
    
    await message.reply_text(
        text="**Please enter the base filename format:**\n\nExample: `Naruto [Dual] [S1] {E01} [480p] @Anime_Sanctum.mkv`",
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & filters.reply & filters.create(force_reply_filter))
async def rename_batch_execute(client, message):
    if not hasattr(client, "file_batch") or not client.file_batch:
        return await message.reply_text("No files in the batch to rename.")

    base_name = message.text
    try:
        start_episode = int(base_name.split("{E")[1].split("}")[0])
    except (IndexError, ValueError):
        return await message.reply_text("Invalid format. Use a format like `Naruto [Dual] [S1] {E01} [480p] @Anime_Sanctum.mkv`.")
    
    for index, (file, msg) in enumerate(client.file_batch):
        episode_number = start_episode + index
        new_name = base_name.replace(f"{start_episode:02}", f"{episode_number:02}")
        
        button = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            button.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
        elif file.media == MessageMediaType.AUDIO:
            button.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

        await msg.reply(
            text=f"**Select the output file type:**\n**• File Name:** `{new_name}`",
            reply_markup=InlineKeyboardMarkup(button)
        )

    client.file_batch = []
    await message.reply_text("Batch processing completed.")

@Client.on_callback_query(filters.regex("upload"))
async def batch_upload_callback(bot, query):
    user_id = query.from_user.id
    file_name = query.message.text.split(":-")[1].strip()
    file_path = f"downloads/{user_id}/{file_name}"
    file = query.message.reply_to_message

    sts = await query.message.edit("Trying to download...")
    try:
        path = await file.download(file_name=file_path, progress=progress_for_pyrogram, progress_args=("Download started...", sts, time.time()))
    except Exception as e:
        return await sts.edit(f"Error: {e}")
    
    duration = 0
    try:
        metadata = extractMetadata(createParser(file_path))
        if metadata.has("duration"):
            duration = metadata.get('duration').seconds
    except:
        pass

    ph_path = None
    try:
        caption = f"**{file_name}**"
        await sts.edit("Trying to upload...")
        if query.data.endswith("document"):
            await query.message.reply_document(
                document=file_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("Upload started...", sts, time.time())
            )
        elif query.data.endswith("video"):
            await query.message.reply_video(
                video=file_path,
                caption=caption,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("Upload started...", sts, time.time())
            )
        elif query.data.endswith("audio"):
            await query.message.reply_audio(
                audio=file_path,
                caption=caption,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("Upload started...", sts, time.time())
            )
    except Exception as e:
        await sts.edit(f"Error: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
        

