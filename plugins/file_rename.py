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


user_batch_states = {}

@Client.on_message(filters.command("batch"))
async def start_batch_rename(client, message):
    """Initialize batch rename process"""
    user_id = message.from_user.id
    
    # Reset the batch state for this user
    user_batch_states[user_id] = {
        'files': [],
        'state': 'waiting_for_files'
    }
    
    await message.reply_text(
        "🔄 Batch Rename Process Started!\n\n"
        "• Send all the files you want to rename\n"
        "• Once done, send /done to proceed"
    )

@Client.on_message(filters.command("done"))
async def process_batch_rename(client, message):
    """Process batch rename when user sends /done"""
    user_id = message.from_user.id
    
    # Check if user has an active batch process
    if user_id not in user_batch_states or user_batch_states[user_id]['state'] == 'waiting_for_files':
        await message.reply_text("No batch rename process active. Start with /batch")
        return
    
    # Check if files exist
    batch_files = user_batch_states[user_id]['files']
    if not batch_files:
        await message.reply_text("No files received. Use /batch to start again.")
        return
    
    # Change state and ask for naming template
    user_batch_states[user_id]['state'] = 'waiting_for_template'
    await message.reply_text(
        "📝 Send the naming template for batch rename\n\n"
        "Example: `Naruto [Dual] [S1] {E01} [480p] @Anime_Sanctum.mkv`\n"
        "Use {E} or {E01} for episode numbering"
    )

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file_upload(client, message):
    user_id = message.from_user.id
    
    # Check file size
    file = getattr(message, message.media.value)
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sorry, files larger than 2GB are not supported")
    
    # Check if batch process is active
    if user_id in user_batch_states and user_batch_states[user_id]['state'] == 'waiting_for_files':
        # Add file to batch
        user_batch_states[user_id]['files'].append(message)
        await message.reply_text(f"File added to batch. Total files: {len(user_batch_states[user_id]['files'])}")
    elif user_id in user_batch_states and user_batch_states[user_id]['state'] == 'waiting_for_template':
        # Ignore files at this stage
        return
    else:
        # Use existing single file rename logic
        await rename_handler(client, message)

@Client.on_message(filters.private & filters.text)
async def handle_batch_template(client, message):
    user_id = message.from_user.id
    
    # Check if user is in batch template waiting state
    if user_id in user_batch_states and user_batch_states[user_id]['state'] == 'waiting_for_template':
        template = message.text
        
        # Validate template
        if '{E}' not in template and '{E01}' not in template:
            await message.reply_text("Invalid template. Must include {E} or {E01}")
            return
        
        # Process batch rename
        batch_files = user_batch_states[user_id]['files']
        
        # Sort files by message ID to maintain order
        batch_files.sort(key=lambda x: x.id)
        
        # Prepare template with formatting
        if '{E}' in template:
            base_template = template.replace('{E}', '{:d}')
        else:
            base_template = template.replace('{E01}', '{:02d}')
        
        # Process each file
        for index, file_message in enumerate(batch_files, start=1):
            try:
                # Generate new filename
                new_name = base_template.format(index)
                
                # Simulate a reply message for existing rename logic
                mock_reply = type('MockReply', (), {
                    'text': new_name,
                    'reply_to_message': file_message,
                    'delete': lambda: None,
                    'chat': file_message.chat,
                    'from_user': file_message.from_user,
                    'id': file_message.id
                })
                
                # Use existing rename selection
                await rename_selection(client, mock_reply)
            
            except Exception as e:
                await message.reply_text(f"Error renaming file {index}: {str(e)}")
        
        # Clear batch state
        del user_batch_states[user_id]
        
        await message.reply_text("✅ Batch rename completed successfully!")
    else:
        # Use existing single file rename logic if not in batch state
        await rename_handler(client, message)
        

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




