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
import re

batch_files = {}
batch_states = {}

def extract_starting_number(format_string):
    """Extract starting number from format string like '{numbering-5}'"""
    match = re.search(r'{numbering-(\d+)}', format_string)
    if match:
        return int(match.group(1))
    return 1

def process_numbering(format_string, index, total_files):
    """Process numbering in format string, handling custom start numbers"""
    # Extract starting number if specified
    start_num = extract_starting_number(format_string)
    
    # Calculate actual number
    actual_number = start_num + index
    
    # Replace both {numbering} and {numbering-X} patterns
    format_string = re.sub(r'{numbering-\d+}', str(actual_number), format_string)
    format_string = format_string.replace('{numbering}', str(actual_number))
    
    return format_string

@Client.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    chat_id = message.chat.id

    if batch_states.get(chat_id, False):
        await message.reply_text("🚫 You're already in batch upload mode. Use /done to finish or /cancel to exit.")
        return

    batch_states[chat_id] = True
    batch_files[chat_id] = []

    await message.reply_text(
        "**Batch Rename Mode Activated**\n\n"
        "Please send the files one by one.\n"
        "Use /done when finished or /cancel to exit.\n\n"
        "For custom numbering start, use format like:\n"
        "`Show Name E{numbering-5}` - starts numbering from 5",
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def handle_file(client, message):
    chat_id = message.chat.id
    
    if not batch_states.get(chat_id):
        return

    file = getattr(message, message.media.value)
    filename = file.file_name

    if file.file_size > 2000 * 1024 * 1024:
        await message.reply_text("Sorry, files larger than 2GB are not supported.")
        return

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

    await message.reply_text(
        "Please provide the batch rename format. Use:\n"
        "• {numbering} for sequential numbering\n"
        "• {numbering-X} to start from number X\n"
        "• {original_name} for original filename\n\n"
        "Example: `Show Name E{numbering-5} [1080p]`",
        reply_markup=ForceReply(True)
    )

async def process_single_file(bot, chat_id, file_data, new_name, upload_type):
    """Process and send a single file immediately after renaming"""
    try:
        file_path = f"downloads/{chat_id}{time.time()}/{new_name}"
        original_file_obj = file_data['file']
        
        # Download file
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

        # Send file immediately
        if upload_type == "document":
            await bot.send_document(
                chat_id,
                document=path,
                thumb=ph_path,
                caption=f"**{new_name}**"
            )
        else:
            await bot.send_video(
                chat_id,
                video=path,
                thumb=ph_path,
                caption=f"**{new_name}**",
                duration=duration
            )

        # Clean up
        try:
            os.remove(path)
            if ph_path:
                os.remove(ph_path)
        except:
            pass

    except Exception as e:
        await bot.send_message(chat_id, f"Error processing file: {str(e)}")

@Client.on_callback_query(filters.regex("batch_upload_"))
async def send_batch_files(bot, query):
    chat_id = query.message.chat.id
    upload_type = query.data.split("_")[-1]
    await query.message.delete()

    batch_info = batch_files.get(chat_id)
    if not batch_info:
        await query.answer("Batch information not found.", show_alert=True)
        return

    status_msg = await bot.send_message(chat_id, "⏳ Processing batch files...")
    total_files = len(batch_info['files'])

    try:
        for idx, file_data in enumerate(batch_info['files']):
            original_file = file_data['original_filename']
            
            # Generate new filename with custom numbering support
            new_name = process_numbering(
                batch_info['format'],
                idx,
                total_files
            ).format(original_name=original_file)

            # Ensure file extension
            if not "." in new_name:
                extn = original_file.rsplit('.', 1)[-1] if "." in original_file else "mkv"
                new_name = f"{new_name}.{extn}"

            # Process and send file immediately
            await process_single_file(bot, chat_id, file_data, new_name, upload_type)
            await status_msg.edit(f"Processed {idx + 1}/{total_files} files")

        await status_msg.delete()
        batch_files.pop(chat_id, None)
        batch_states[chat_id] = False

    except Exception as e:
        await status_msg.edit(f"Batch processing error: {str(e)}")
