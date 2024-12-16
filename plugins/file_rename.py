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


# @Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
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
 
# @Client.on_message(filters.private & filters.reply & filters.create(force_reply_filter))
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
batch_states = {}
batch_files = {}

# Custom filter to check batch upload state
def batch_filter():
    async def func(_, __, message):
        return batch_states.get(message.chat.id, False)
    return filters.create(func)

# Start Batch Mode
@Client.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    chat_id = message.chat.id

    if batch_states.get(chat_id, False):
        await message.reply_text("⚠️ You are already in batch upload mode. Use /done to finish or /cancel to exit.")
        return

    batch_states[chat_id] = True
    batch_files[chat_id] = []

    await message.reply_text(
        "**Batch Upload Mode Activated**\n\nSend files sequentially (e.g., Episode 1, Episode 2).\nUse /done to finish or /cancel to exit.",
        reply_to_message_id=message.id
    )

# Collect Files in Batch
@Client.on_message(filters.private & (filters.document | filters.audio | filters.video) & batch_filter())
async def collect_batch_files(client, message):
    chat_id = message.chat.id
    file = getattr(message, message.media.value)

    # Store file metadata
    batch_files[chat_id].append({
        "file_id": file.file_id,
        "file_name": file.file_name,
        "file_size": file.file_size,
        "thumb_id": file.thumbs[0].file_id if file.thumbs else None
    })

    await message.reply_text(f"✅ File added to batch ({len(batch_files[chat_id])} files).")

# Finish Batch and Rename Files
@Client.on_message(filters.command("done") & filters.private)
async def finish_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("⚠️ You're not in batch upload mode. Use /batch to start.")
        return

    if not batch_files[chat_id]:
        await message.reply_text("⚠️ No files were added. Use /batch to start again.")
        return

    # Ask for naming format
    reply = await message.reply_text(
        "✏️ Please provide the naming format (use `{numbering}` for sequence numbers):\n\nExample: `Episode {numbering}.mkv`",
        reply_markup=ForceReply(True)
    )

    # Wait for user to reply with format
    @Client.on_message(filters.private & filters.reply & filters.create(lambda _, __, msg: msg.reply_to_message == reply))
    async def batch_rename_handler(_, rename_message):
        name_format = rename_message.text

        if "{numbering}" not in name_format:
            await rename_message.reply_text("⚠️ Invalid format. Make sure to include `{numbering}`.")
            return

        # Ask for send options
        buttons = [
            [InlineKeyboardButton("📁 Send as Document", callback_data="batch_send_document")],
            [InlineKeyboardButton("🎥 Send as Video", callback_data="batch_send_video")]
        ]
        await rename_message.reply_text(
            "**How would you like to send the renamed files?**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        # Store batch info
        batch_states[chat_id] = False
        batch_files[chat_id] = {
            "files": batch_files[chat_id],
            "name_format": name_format
        }

# Handle Batch Send Options
@Client.on_callback_query(filters.regex("batch_send_.*"))
async def send_batch_files(client, query):
    chat_id = query.message.chat.id
    data = query.data
    send_as_video = data == "batch_send_video"

    batch_info = batch_files.get(chat_id, None)
    if not batch_info:
        await query.answer("No batch data found.", show_alert=True)
        return

    files = batch_info["files"]
    name_format = batch_info["name_format"]
    await query.message.edit("⏳ Processing batch files...")

    for idx, file_data in enumerate(files, start=1):
        try:
            # Download the file
            file_path = await client.download_media(file_data["file_id"])
            new_name = name_format.replace("{numbering}", str(idx))
            new_path = os.path.join(os.path.dirname(file_path), new_name)
            os.rename(file_path, new_path)

            # Download thumbnail if available
            thumb_path = None
            if file_data.get("thumb_id"):
                thumb_path = await client.download_media(file_data["thumb_id"])

            # Send file
            if send_as_video:
                await client.send_video(
                    chat_id,
                    video=new_path,
                    thumb=thumb_path if thumb_path else None,
                    caption=f"**{new_name}**"
                )
            else:
                await client.send_document(
                    chat_id,
                    document=new_path,
                    thumb=thumb_path if thumb_path else None,
                    caption=f"**{new_name}**"
                )

            # Cleanup
            os.remove(new_path)
            if thumb_path:
                os.remove(thumb_path)

        except Exception as e:
            await query.message.reply_text(f"⚠️ Error processing file {idx}: {e}")

    # Clear batch state
    batch_files.pop(chat_id, None)
    await query.message.reply_text("✅ Batch processing completed.")

# Cancel Batch Mode
@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("⚠️ You're not in batch upload mode.")
        return

    batch_states.pop(chat_id, None)
    batch_files.pop(chat_id, None)
    await message.reply_text("❌ Batch mode cancelled.")

