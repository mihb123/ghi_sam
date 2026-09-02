"""Lop van chuyen Telegram: nhan update -> goi core.Engine -> gui lai tin nhan.

Dung 1 MessageHandler cho moi tin nhan text (ke ca tin bat dau bang '/') vi core.Engine
tu phan tich lenh; set_my_commands chi de hien menu goi y trong Telegram.
"""

import logging

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, filters

from ..core import Engine, Incoming
from ..render import TelegramFmt, split_message
from ..text import strip_bot_mention

logger = logging.getLogger(__name__)

MENU = [
    ("start", "Hướng dẫn sử dụng"),
    ("nguoichoi", "Khai báo người chơi theo thứ tự chỗ"),
    ("dsnguoi", "Xem danh sách người chơi"),
    ("themnguoi", "Thêm 1 người chơi"),
    ("xoanguoi", "Bỏ 1 người chơi"),
    ("banmoi", "Mở bàn chơi mới"),
    ("ketthuc", "Chốt bàn đang chơi"),
    ("v", "Ghi 1 ván"),
    ("sua", "Nhập lại 1 ván"),
    ("undo", "Hủy ván vừa ghi"),
    ("xoa", "Xóa ván theo số"),
    ("khoiphuc", "Lấy lại ván đã xóa"),
    ("tong", "Điểm lũy kế bàn đang chơi"),
    ("lichsu", "Các ván gần nhất"),
    ("chiase", "Lấy link mời bạn bè dùng bot"),
    ("sheet", "Xem/đặt link Google Sheet"),
    ("export", "Ghi bàn đang chơi lên Google Sheet"),
]


# Goi sau app.initialize(): dang ky menu lenh va canh bao Group Privacy.
def build_application(token: str, engine: Engine) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["engine"] = engine
    app.add_handler(MessageHandler(filters.TEXT, _on_message))
    app.add_error_handler(_on_error)
    return app


# Tra ve username cua bot: lenh /chiase can no de dung deep link t.me/<bot>?start=...
async def setup(app: Application) -> str | None:
    await app.bot.set_my_commands([BotCommand(c, d) for c, d in MENU])

    # Group Privacy con bat thi trong group bot chi thay lenh co '/', khong thay '-5, 5, , 6'.
    me = await app.bot.get_me()
    logger.info("Telegram: @%s (id %s)", me.username, me.id)
    if not me.can_read_all_group_messages:
        logger.warning(
            "Group Privacy dang BAT: trong group bot chi nhan duoc lenh co '/', tin nhan tran "
            "nhu '-5, 5, , 6' se bi bo qua. Tat tai @BotFather -> /mybots -> chon bot -> "
            "Bot Settings -> Group Privacy -> Turn off (chat rieng voi bot van chay binh thuong)."
        )
    else:
        # Co nay la cai dat toan cuc; Telegram chot quyen doc cho tung group ngay luc bot vao
        # nen group them truoc khi tat van loc tin nhan tran. Khong co API nao doc duoc trang
        # thai per-group, chi nhac duoc.
        logger.info(
            "Group Privacy dang TAT. Neu group nao chi nhan duoc lenh co '/', group do da them "
            "bot tu truoc khi tat: kick bot ra roi them lai, hoac cap quyen admin cho bot."
        )
    return me.username


async def _on_message(update: Update, context) -> None:
    message = update.message
    if message is None or not message.text:
        return

    engine: Engine = context.application.bot_data["engine"]
    fmt = TelegramFmt()
    chat, user = update.effective_chat, update.effective_user
    logger.info("Telegram <- chat %s (%s): %r", chat.id, chat.type, message.text)
    replies = await engine.handle(
        Incoming(
            platform="telegram",
            native_chat_id=str(chat.id),
            chat_title=chat.title,
            text=strip_bot_mention(message.text, context.bot.username),
            author=user.full_name if user else None,
            native_user_id=str(user.id) if user else None,
            username=user.username if user else None,
            chat_type=chat.type,
        ),
        fmt,
    )
    for reply in replies:
        for chunk in split_message(reply, fmt.limit):
            await message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def _on_error(update: object, context) -> None:
    logger.exception("Telegram handler loi", exc_info=context.error)
