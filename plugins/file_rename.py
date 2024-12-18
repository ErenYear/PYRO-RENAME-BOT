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

@Client.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    chat_id = message.chat.id

    if batch_states.get(chat_id, False):
        await message.reply_text("🚫 You're already in batch upload mode. Use /cancel to exit.")
        return

    batch_states[chat_id] = {
        'files': [],
        'format': None,
        'start_number': 1
    }

    await message.reply_text(
        "**Batch Rename Mode Activated**\n\nSend the files one by one.\n"
        "Use /done to finish or /cancel to exit.",
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video) & filters.create(lambda _, __, m: batch_states.get(m.chat.id)))
async def collect_and_rename(client, message):
    chat_id = message.chat.id
    state = batch_states.get(chat_id)

    if not state:
        return

    # Get file details
    file = getattr(message, message.media.value)
    filename = file.file_name

    if file.file_size > 2000 * 1024 * 1024:
        await message.reply_text("🚫 Files larger than 2GB are not supported.")
        return

    # If renaming format is not provided yet
    if state['format'] is None:
        state['files'].append({
            'file': message,
            'original_filename': filename
        })
        await message.reply_text(
            "Send renaming format (use {numbering} for numbering):\n"
            "Example: `Classroom Of The Elite [Dual] [S1] E{numbering} [360p]`",
            reply_markup=ForceReply(True)
        )
        return

    # Generate new filename
    new_number = state['start_number'] + len(state['files'])
    new_name = state['format'].format(numbering=new_number, original_name=filename)

    # Ensure file extension
    if "." not in new_name:
        extn = filename.rsplit('.', 1)[-1] if "." in filename else "mkv"
        new_name = f"{new_name}.{extn}"

    # Process and send the file immediately
    await process_file(client, message, new_name, chat_id)
    state['files'].append(new_name)

@Client.on_message(filters.private & filters.reply & filters.text)
async def set_format(client, message):
    chat_id = message.chat.id
    state = batch_states.get(chat_id)

    if not state or state['format']:
        return

    # Validate format
    if "{numbering}" not in message.text:
        await message.reply_text("🚫 Invalid format. Must include `{numbering}`.")
        return

    # Get starting number
    try:
        start_number = int(message.text.split("-")[-1].strip())
    except ValueError:
        start_number = 1

    state['format'] = message.text.split("-")[0].strip()
    state['start_number'] = start_number

    await message.reply_text("✅ Format set! Send your files now.")

async def process_file(client, message, new_name, chat_id):
    file = getattr(message, message.media.value)

    try:
        file_path = f"downloads/{chat_id}{time.time()}/{new_name}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Download file
        path = await file.download(file_name=file_path)

        # Extract metadata
        duration = 0
        try:
            metadata = extractMetadata(createParser(path))
            if metadata.has("duration"):
                duration = metadata.get("duration").seconds
        except:
            pass

        # Handle thumbnail
        ph_path = None
        media = getattr(message, message.media.value)
        db_thumb = await db.get_thumbnail(chat_id)

        if media.thumbs or db_thumb:
            if db_thumb:
                ph_path = await client.download_media(db_thumb)
            else:
                ph_path = await client.download_media(media.thumbs[0].file_id)

            Image.open(ph_path).convert("RGB").save(ph_path)
            img = Image.open(ph_path)
            img.resize((320, 320))
            img.save(ph_path, "JPEG")

        # Send the file
        await client.send_document(
            chat_id,
            document=path,
            thumb=ph_path,
            caption=f"**{new_name}**",
            progress=progress_for_pyrogram,
            progress_args=("Uploading...", message, time.time())
        )

        # Clean up
        os.remove(path)
        if ph_path:
            os.remove(ph_path)

    except Exception as e:
        await message.reply_text(f"🚫 Error processing file: {str(e)}")

@Client.on_message(filters.command("done") & filters.private)
async def finish_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("🚫 No active batch. Use /batch to start.")
        return

    batch_states.pop(chat_id, None)
    await message.reply_text("✅ Batch rename completed.")

@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("🚫 No active batch. Use /batch to start.")
        return

    batch_states.pop(chat_id, None)
    await message.reply_text("❌ Batch upload canceled.")

