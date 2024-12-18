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
async def collect_and_process_file(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        return

    file = getattr(message, message.media.value)
    filename = file.file_name

    if file.file_size > 2000 * 1024 * 1024:
        await message.reply_text("Sorry, files larger than 2GB are not supported.")
        return

    batch_files[chat_id].append({'file': message, 'original_filename': filename})
    await message.reply_text("File added to batch. Please provide the rename format. Use {numbering} for numbering.")

@Client.on_message(filters.private & filters.reply, group=1)
async def rename_and_send_file(client, message):
    chat_id = message.chat.id
    format_text = message.text

    if "{numbering}" not in format_text:
        await message.reply_text("🚫 Invalid format. Must include {numbering}.")
        return

    files = batch_files.get(chat_id, [])
    if not files:
        await message.reply_text("No files found to process.")
        return

    start_number = 1
    if "-n" in format_text:
        try:
            start_number = int(format_text.split("-n")[-1].strip())
            format_text = format_text.split("-n")[0].strip()
        except ValueError:
            await message.reply_text("🚫 Invalid numbering start value.")
            return

    for idx, file_data in enumerate(files, start=start_number):
        original_file = file_data["original_filename"]
        new_name = format_text.format(numbering=idx, original_name=original_file)

        if "." not in new_name:
            extn = original_file.rsplit(".", 1)[-1] if "." in original_file else "mkv"
            new_name = f"{new_name}.{extn}"

        file_path = f"downloads/{chat_id}{time.time()}/{new_name}"
        original_file_obj = file_data["file"]

        try:
            path = await original_file_obj.download(file_name=file_path)

            duration = 0
            try:
                metadata = extractMetadata(createParser(path))
                if metadata.has("duration"):
                    duration = metadata.get("duration").seconds
            except:
                pass

            ph_path = None
            media = getattr(original_file_obj, original_file_obj.media.value)
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

            await client.send_document(
                chat_id,
                document=path,
                thumb=ph_path,
                caption=f"**{new_name}**",
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", None, time.time())
            )

            os.remove(path)
            if ph_path:
                os.remove(ph_path)
        except Exception as e:
            await message.reply_text(f"Error processing file: {str(e)}")

    batch_files.pop(chat_id, None)
    await message.reply_text("Batch processing completed!")

@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("🚫 You're not in batch upload mode. Use /batch to start.")
        return

    batch_states.pop(chat_id, None)
    batch_files.pop(chat_id, None)
    await message.reply_text("❌ Batch upload cancelled.")
    
