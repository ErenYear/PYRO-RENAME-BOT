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

'''
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
'''

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

# Shared storage for batch processing
batch_files = {}
batch_states = {}

# Custom filter to handle batch upload state
def batch_filter():
    async def func(_, __, message):
        return batch_states.get(message.chat.id, False)
    return filters.create(func)

@Client.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    chat_id = message.chat.id

    if batch_states.get(chat_id, False):
        await message.reply_text("🚫 You're already in batch upload mode. Use /done to finish or /cancel to exit.")
        return

    batch_states[chat_id] = True
    batch_files[chat_id] = []

    await message.reply_text(
        "**Batch Rename Mode Activated**\n\nPlease send the files one by one.\nUse /done when finished or /cancel to exit.",
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video) & batch_filter())
async def collect_batch_file(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        return

    file = getattr(message, message.media.value)
    filename = file.file_name

    if file.file_size > 2000 * 1024 * 1024:
        await message.reply_text("Sorry, files larger than 2GB are not supported.")
        return

    # Store file information for batch processing
    batch_files[chat_id].append({
        'file': message,
        'original_filename': filename
    })

    await message.reply_text(f"Added file {len(batch_files[chat_id])} to batch.")

@Client.on_message(filters.command("done") & filters.private)
async def finish_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("🚫 You're not in batch upload mode. Use /batch to start.")
        return

    if not batch_files[chat_id]:
        await message.reply_text("🚫 No files received in batch mode. Use /batch to restart.")
        return

    # Ask for batch renaming format
    await message.reply_text(
        "Please provide the batch rename format. Use {numbering} for episode/file numbers.\n\n"
        "Example: Episode {numbering} - {original_name}",
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & filters.reply & filters.create(force_reply_filter))
async def process_batch_rename(client, message):
    chat_id = message.chat.id
    batch_format = message.text

    if not batch_states.get(chat_id):
        return

    # Validate format
    if "{numbering}" not in batch_format:
        await message.reply_text("🚫 Invalid format. Must include {numbering}.")
        return

    # Prepare upload options
    button = [
        [InlineKeyboardButton("📁 Document", callback_data="batch_upload_document")],
        [InlineKeyboardButton("🎥 Video", callback_data="batch_upload_video")]
    ]

    await message.reply_text(
        "**Select Batch Upload Type**",
        reply_markup=InlineKeyboardMarkup(button)
    )

    # Store batch information
    batch_files[chat_id] = {
        'files': batch_files[chat_id],
        'format': batch_format
    }
    batch_states[chat_id] = False

@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("🚫 You're not in batch upload mode. Use /batch to start.")
        return

    batch_states.pop(chat_id, None)
    batch_files.pop(chat_id, None)
    await message.reply_text("❌ Batch upload cancelled.")

@Client.on_callback_query(filters.regex("batch_upload_"))
async def send_batch_files(bot, query):
    chat_id = query.message.chat.id
    upload_type = query.data.split("_")[-1]
    await query.message.delete()

    # Get stored batch info
    batch_info = batch_files.get(chat_id)
    if not batch_info:
        await query.answer("Batch information not found.", show_alert=True)
        return

    status_msg = await bot.send_message(chat_id, "⏳ Processing batch files...")

    try:
        for idx, file_data in enumerate(batch_info['files'], start=1):
            # Generate new filename
            original_file = file_data['original_filename']
            new_name = batch_info['format'].format(
                numbering=idx, 
                original_name=original_file
            )

            # Ensure file extension
            if not "." in new_name:
                extn = original_file.rsplit('.', 1)[-1] if "." in original_file else "mkv"
                new_name = f"{new_name}.{extn}"

            # Download file
            file_path = f"downloads/{chat_id}{time.time()}/{new_name}"
            original_file_obj = file_data['file']
            
            # Download and process similar to the original rename logic
            try:
                path = await original_file_obj.download(file_name=file_path)
                
                # Extract metadata
                duration = 0
                try:
                    metadata = extractMetadata(createParser(path))
                    if metadata.has("duration"): 
                        duration = metadata.get('duration').seconds
                except:
                    pass

                # Handle thumbnail
                ph_path = None
                media = getattr(original_file_obj, original_file_obj.media.value)
                db_thumb = await db.get_thumbnail(chat_id)

                if media.thumbs or db_thumb:
                    if db_thumb:
                        ph_path = await bot.download_media(db_thumb)
                    else:
                        ph_path = await bot.download_media(media.thumbs[0].file_id)
                    
                    Image.open(ph_path).convert("RGB").save(ph_path)
                    img = Image.open(ph_path)
                    img.resize((320, 320))
                    img.save(ph_path, "JPEG")

                # Upload file based on type
                if upload_type == "document":
                    await bot.send_document(
                        chat_id, 
                        document=path, 
                        thumb=ph_path, 
                        caption=f"**{new_name}**",
                        progress=progress_for_pyrogram,
                        progress_args=("Upload Started...", status_msg, time.time())
                    )
                elif upload_type == "video":
                    await bot.send_video(
                        chat_id, 
                        video=path, 
                        thumb=ph_path, 
                        caption=f"**{new_name}**",
                        duration=duration,
                        progress=progress_for_pyrogram,
                        progress_args=("Upload Started...", status_msg, time.time())
                    )

                # Clean up files
                try:
                    os.remove(path)
                    if ph_path:
                        os.remove(ph_path)
                except:
                    pass

            except Exception as e:
                await bot.send_message(chat_id, f"Error processing file {idx}: {str(e)}")

        await status_msg.delete()
        batch_files.pop(chat_id, None)

    except Exception as e:
        await status_msg.edit(f"Batch upload error: {str(e)}")
