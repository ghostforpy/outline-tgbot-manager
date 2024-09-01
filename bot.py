import os
import requests
import json
import dotenv
import logging
from telegram import Update, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from outline_vpn.outline_vpn import OutlineVPN

from utils import convert_size, group


dotenv.load_dotenv()

ADMIN = os.environ.get("admins", None)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def get_keys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ADMIN is not None and str(update.message.from_user.id) not in ADMIN:
        return

    keys = context.bot_data["outline"].get_keys()

    k_html = list(
        map(
            lambda x: f"{x.key_id}) <b>{x.name}</b> ({convert_size(x.used_bytes)}) : <code>{x.access_url}</code>\n",
            keys,
        )
    )

    for i in group(k_html, 10):
        await update.message.reply_html(
            "\n".join([f"Total Keys Created: {len(k_html)}", ""] + i)
        )


async def create_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ADMIN is not None and str(update.message.from_user.id) not in ADMIN:
        return
    context.user_data["mode"] = "create"
    await update.message.reply_html("Введите имя нового ключа")


async def delete_key_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if ADMIN is not None and str(update.message.from_user.id) not in ADMIN:
        return

    keys = context.bot_data["outline"].get_keys()

    await update.message.reply_html(
        "Выберите ключ для удаления",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"{key.key_id} - {key.name}",
                        callback_data=f"delete_key-{key.key_id}",
                    )
                ]
                for key in keys
            ]
        ),
    )


async def delete_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    if ADMIN is not None and str(update.callback_query.from_user.id) not in ADMIN:
        return

    key_id: str = update.callback_query.data.split("-")[1]

    if key_id.isnumeric():
        response = context.application.bot_data["outline"].delete_key(int(key_id))

        if response:
            await update.callback_query.message.reply_html(
                f"Key ID <b>{key_id}</b> DELETED!"
            )
        else:
            await update.callback_query.message.reply_html(
                f"Couldn't delete Key ID <b>{key_id}</b>!"
            )


async def get_server_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    outline: OutlineVPN = context.application.bot_data["outline"]
    info = outline.get_server_information()
    await update.message.reply_html(
        "\n".join(f"<b>{key}</b>: <pre>{value}</pre>" for key, value in info.items())
    )


async def rename_key_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if ADMIN is not None and str(update.message.from_user.id) not in ADMIN:
        return

    keys = context.bot_data["outline"].get_keys()

    await update.message.reply_html(
        "Выберите ключ для переименования",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"{key.key_id} - {key.name}",
                        callback_data=f"rename_key-{key.key_id}",
                    )
                ]
                for key in keys
            ]
        ),
    )


async def wait_rename_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    key_id: str = update.callback_query.data.split("-")[1]
    context.user_data["mode"] = "rename"
    context.user_data["key_id"] = key_id
    await update.callback_query.message.reply_html("Введите новое имя ключа")


async def get_transferred_data(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    outline: OutlineVPN = context.application.bot_data["outline"]

    try:
        data = outline.get_transferred_data()
        logger.info(data)
        await update.message.reply_html(
            f"Total Transferred Data: <b>{convert_size(sum(data['bytesTransferredByUserId'].values()))}</b>"
        )
    except Exception as e:
        logger.warning(e)
        await update.message.reply_html(f"Error Occured!")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("message_handler")
    if ADMIN is not None and str(update.message.from_user.id) not in ADMIN:
        return
    mode = context.user_data.pop("mode", "")
    if mode not in ["rename", "create"]:
        await update.message.reply_html("Неправильная команда")
        return

    outline: OutlineVPN = context.bot_data["outline"]
    if mode == "rename":
        key_id: str = context.user_data.pop("key_id", "None")
        if not key_id.isnumeric() or key_id not in [
            i.key_id for i in context.bot_data["outline"].get_keys()
        ]:
            await update.message.reply_html("Неправильный key id")
            return
        response = outline.rename_key(key_id, update.message.text)
        if response:
            await update.message.reply_html(
                f"Key ID <b>{key_id}</b> renamed to -> <b>{update.message.text}</b>"
            )
        else:
            await update.message.reply_html(f"Couldn't rename!")
    elif mode == "create":
        try:
            key = context.bot_data["outline"].create_key(update.message.text)
            await update.message.reply_html(
                f"Key <b>{key.name}</b> Created: <code>{key.access_url}</code>"
            )
        except:
            await update.message.reply_html("Couldn't create the key!")



BOT_COMMANDS = [
    BotCommand("get_keys", "Активные ключи"),
    BotCommand("create_key", "Создать новый ключ"),
    BotCommand("rename_key", "Переименовать ключ"),
    BotCommand("delete_key", "Удалить ключ"),
    BotCommand("get_server_info", "Инормация о сервере"),
    BotCommand("get_transferred_data", "Информация о переданных данных"),
]


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(os.environ["TOKEN"]).build()

    application.bot_data["outline"] = OutlineVPN(os.environ["api_url"], cert_sha256=os.environ["certSha256"])

    application.add_handler(CommandHandler("get_keys", get_keys))
    application.add_handler(CommandHandler("create_key", create_key))
    application.add_handler(CommandHandler("delete_key", delete_key_command))
    application.add_handler(CommandHandler("get_server_info", get_server_info))
    application.add_handler(CommandHandler("rename_key", rename_key_command))
    application.add_handler(
        CommandHandler("get_transferred_data", get_transferred_data)
    )
    application.add_handler(
        CallbackQueryHandler(delete_key, pattern="^delete_key-\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(wait_rename_key, pattern="^rename_key-\d+$")
    )
    application.add_handler(MessageHandler(filters.TEXT, message_handler))

    request = requests.post(
        f"https://api.telegram.org/bot{os.environ['TOKEN']}/setMyCommands",
        data={"commands": json.dumps([i.to_dict() for i in BOT_COMMANDS])},
    )
    logger.info(f"SET COMMANDS {request}")

    application.run_polling()


if __name__ == "__main__":
    main()
