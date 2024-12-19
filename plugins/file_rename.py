from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram
from helper.database import db
from PIL import Image
import os, time

batch_files = {}
batch_states = {}
upload_type = {}
sts = {}

# Custom filter to handle batch upload state
def batch_filter():
    async def func(_, __, message):
        return batch_states.get(message.chat.id, False)
    return filters.create(func)

@Client.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    chat_id = message.chat.id

    if batch_states.get(chat_id, False):
        await message.reply_text("🚫 You're already in batch upload mode. Use /cancel to exit.")
        return

    batch_states[chat_id] = True
    batch_files[chat_id] = []
    await message.reply_text(
        "**Batch Rename Mode Activated**\n\nSend files one by one.\nUse /cancel to exit.",
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
    await message.reply_text("File added to batch. Please provide the rename format with `-n` for numbering.")

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

    button = [
        [InlineKeyboardButton("📁 Document", callback_data="upload_document")],
        [InlineKeyboardButton("🎥 Video", callback_data="upload_video")]
    ]
    await message.reply_text(
        "Select upload type:",
        reply_markup=InlineKeyboardMarkup(button)
    )

    upload_type[chat_id] = {'format': format_text, 'start_number': start_number}

@Client.on_callback_query(filters.regex("upload_"))
async def process_file_upload(client, query):
    chat_id = query.message.chat.id
    file_type = query.data.split("_")[1]

    if chat_id not in upload_type:
        await query.answer("No rename format found.", show_alert=True)
        return

    await query.message.delete()
    format_text = upload_type[chat_id]['format']
    start_number = upload_type[chat_id]['start_number']
    files = batch_files[chat_id]

    sts_msg = await client.send_message(chat_id, "Starting file uploads...")

    for idx, file_data in enumerate(files, start=start_number):
        original_file = file_data["original_filename"]
        new_name = format_text.format(numbering=idx, original_name=original_file)

        if "." not in new_name:
            extn = original_file.rsplit(".", 1)[-1] if "." in original_file else "mkv"
            new_name = f"{new_name}.{extn}"

        file_path = f"downloads/{chat_id}{time.time()}/{new_name}"
        original_file_obj = file_data["file"]

        try:
            sts[chat_id] = await sts_msg.edit_text(f"Downloading: **{original_file}**")
            path = await original_file_obj.download(
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=(sts[chat_id], "Downloading...", time.time())
            )

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

            sts[chat_id] = await sts_msg.edit_text(f"Uploading: **{new_name}**")

            if file_type == "document":
                await client.send_document(
                    chat_id,
                    document=path,
                    thumb=ph_path,
                    caption=f"**{new_name}**",
                    progress=progress_for_pyrogram,
                    progress_args=(sts[chat_id], "Uploading...", time.time())
                )
            elif file_type == "video":
                await client.send_video(
                    chat_id,
                    video=path,
                    thumb=ph_path,
                    caption=f"**{new_name}**",
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=(sts[chat_id], "Uploading...", time.time())
                )

            os.remove(path)
            if ph_path:
                os.remove(ph_path)
        except Exception as e:
            await client.send_message(chat_id, f"Error processing file: {str(e)}")

    del batch_files[chat_id]
    del upload_type[chat_id]
    sts.pop(chat_id, None)
    await client.send_message(chat_id, "All files have been renamed and uploaded!")

@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_batch(client, message):
    chat_id = message.chat.id

    if not batch_states.get(chat_id):
        await message.reply_text("🚫 You're not in batch upload mode. Use /batch to start.")
        return

    batch_states.pop(chat_id, None)
    batch_files.pop(chat_id, None)
    upload_type.pop(chat_id, None)
    sts.pop(chat_id, None)
    await message.reply_text("❌ Batch upload cancelled.")

