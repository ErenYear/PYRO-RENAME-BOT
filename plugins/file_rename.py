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


batch_states = {}

@Client.on_message(filters.command("batch"))
async def start_batch_rename(client, message):
    """Initialize batch renaming process"""
    user_id = message.from_user.id
    
    # Reset any existing batch state for this user
    batch_states[user_id] = {
        'files': [],
        'status': 'waiting_for_files'
    }
    
    await message.reply_text(
        "🔄 Batch Rename Mode Activated!\n\n"
        "• Send all the files you want to rename\n"
        "• After sending files, I'll ask for a naming template\n"
        "• Use {E} or {E01} in the template to add episode numbers\n"
        "• Send /cancel to stop batch renaming"
    )

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def handle_batch_or_single_file(client, message):
    user_id = message.from_user.id
    
    # Check file size limit
    file = getattr(message, message.media.value)
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sᴏʀʀy Bʀᴏ Tʜɪꜱ Bᴏᴛ Iꜱ Dᴏᴇꜱɴ'ᴛ Sᴜᴩᴩᴏʀᴛ Uᴩʟᴏᴀᴅɪɴɢ Fɪʟᴇꜱ Bɪɢɢᴇʀ Tʜᴀɴ 2Gʙ")
    
    # Check if user is in batch mode
    if user_id in batch_states and batch_states[user_id]['status'] == 'waiting_for_files':
        # Add file to batch
        batch_states[user_id]['files'].append(message)
        await message.reply_text(f"File added to batch. Total files: {len(batch_states[user_id]['files'])}")
        return
    
    # If not in batch mode, use existing single file rename logic
    try:
        await message.reply_text(
            text=f"**__Pʟᴇᴀꜱᴇ Eɴᴛᴇʀ Nᴇᴡ Fɪʟᴇɴᴀᴍᴇ...__**\n\n**Oʟᴅ Fɪʟᴇ Nᴀᴍᴇ** :- `{file.file_name}`",
            reply_to_message_id=message.id,  
            reply_markup=ForceReply(True)
        )       
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**__Pʟᴇᴀꜱᴇ Eɴᴛᴇʀ Nᴇᴡ Fɪʟᴇɴᴀᴍᴇ...__**\n\n**Oʟᴅ Fɪʟᴇ Nᴀᴍᴇ** :- `{file.file_name}`",
            reply_to_message_id=message.id,  
            reply_markup=ForceReply(True)
        )

@Client.on_message(filters.private & filters.text)
async def handle_batch_template(client, message):
    user_id = message.from_user.id
    
    # Check if user is in batch mode
    if user_id not in batch_states or batch_states[user_id]['status'] != 'waiting_for_files':
        return
    
    # Check for cancel command
    if message.text.lower() == '/cancel':
        del batch_states[user_id]
        await message.reply_text("Batch rename process cancelled.")
        return
    
    # Check if the message contains episode template
    if '{e}' not in message.text.lower():
        await message.reply_text("Please include {E} or {E01} in your template for episode numbering.")
        return
    
    # Prepare for batch renaming
    files = batch_states[user_id]['files']
    
    # Prepare the template (replace {E} with a formatter)
    template = message.text
    base_template = template.replace('{E}', '{:02d}').replace('{E01}', '{:02d}')
    
    # Process each file
    for index, file_message in enumerate(files):
        # Calculate episode number
        episode_number = index + 1
        
        # Generate new filename
        new_name = base_template.format(episode_number)
        
        # Create a mock message for existing rename logic
        mock_message = type('MockMessage', (), {
            'text': new_name,
            'delete': lambda: None,
            'reply_to_message': file_message,
            'chat': file_message.chat,
            'from_user': file_message.from_user,
            'id': file_message.id
        })()
        
        # Trigger existing rename selection
        try:
            await rename_selection(client, mock_message)
        except Exception as e:
            await message.reply_text(f"Error renaming file: {e}")
    
    # Clear batch state
    del batch_states[user_id]
    await message.reply_text("Batch renaming completed successfully!")
    

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




