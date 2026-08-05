import os
import logging
import threading
from datetime import datetime

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", "8080"))

# ---------- ذخیره‌سازی در حافظه (بدون دیتابیس) ----------
# توجه: با هر ری‌استارت سرویس، این اطلاعات پاک می‌شن.
users = {}              # user_id -> dict اطلاعات کاربر
tickets = {}             # ticket_id -> dict تیکت پشتیبانی
ticket_counter = {"value": 0}
pending_reps = {}        # user_id -> یوزرنیم درخواست نمایندگی

VOLUME_PLANS = {
    "5gb": {"label": "🔵 ۵ گیگ", "price": 5000},
    "10gb": {"label": "🔵 ۱۰ گیگ", "price": 8000},
    "20gb": {"label": "🔵 ۲۰ گیگ", "price": 14000},
    "50gb": {"label": "🔵 ۵۰ گیگ", "price": 30000},
}

TIME_PLANS = {
    "1m": {"label": "🟢 ۱ ماه", "price": 15000},
    "3m": {"label": "🟢 ۳ ماه", "price": 40000},
    "6m": {"label": "🟢 ۶ ماه", "price": 70000},
    "12m": {"label": "🟢 ۱ سال", "price": 120000},
}

CARD_INFO = (
    "💳 اطلاعات کارت:\n"
    "شماره کارت: 6037-XXXX-XXXX-XXXX\n"
    "به نام: ---\n\n"
    "بعد از واریز، عکس رسید رو ارسال کن."
)

GUIDE_TEXT = (
    "📖 آموزش اتصال به کانفیگ:\n\n"
    "۱️⃣ فایل کانفیگ دریافتی را ذخیره کنید\n"
    "۲️⃣ اپلیکیشن مورد نظر را اجرا کنید\n"
    "۳️⃣ گزینه Import Config را انتخاب کنید\n"
    "۴️⃣ فایل کانفیگ را انتخاب کنید\n"
    "۵️⃣ دکمه Connect را بزنید\n\n"
    "⚠️ نکات مهم:\n"
    "- حتماً اینترنت خود را بررسی کنید\n"
    "- در صورت مشکل، اپلیکیشن را ریستارت کنید\n"
    "- اگر ارور داد، از پشتیبانی کمک بگیرید"
)


# ---------- توابع کمکی ----------
def get_or_create_user(user_id: int, username: str) -> dict:
    if user_id not in users:
        users[user_id] = {
            "username": username,
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
    else:
        users[user_id]["last_active"] = datetime.now().isoformat()
    return users[user_id]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📌 خرید اشتراک", callback_data="menu_buy")],
        [InlineKeyboardButton("🟢 پشتیبانی", callback_data="menu_support")],
        [InlineKeyboardButton("📖 آموزش", callback_data="menu_guide")],
        [InlineKeyboardButton("🟣 درخواست نمایندگی", callback_data="menu_rep")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔴 بازگشت", callback_data="menu_main")]]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔴 انصراف", callback_data="menu_main")]]
    )


def buy_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔵 اشتراک حجمی", callback_data="buy_volume")],
        [InlineKeyboardButton("🟢 اشتراک زمانی", callback_data="buy_time")],
        [InlineKeyboardButton("🔴 بازگشت", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def plans_keyboard(plans: dict, prefix: str) -> InlineKeyboardMarkup:
    keyboard = []
    for key, plan in plans.items():
        text = f"{plan['label']} - {plan['price']:,} تومان"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"{prefix}_{key}")])
    keyboard.append([InlineKeyboardButton("🔴 بازگشت", callback_data="menu_buy")])
    return InlineKeyboardMarkup(keyboard)


# ---------- هندلرها ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or user.first_name)
    context.user_data.clear()
    text = (
        f"سلام {user.first_name} 👋\n"
        "به ربات فروش کانفیگ خوش اومدی.\n"
        "یکی از گزینه‌ها رو انتخاب کن:"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    get_or_create_user(user_id, query.from_user.username or query.from_user.first_name)

    if data == "menu_main":
        context.user_data.clear()
        await query.edit_message_text("منوی اصلی:", reply_markup=main_menu_keyboard())

    elif data == "menu_buy":
        await query.edit_message_text(
            "نوع اشتراک رو انتخاب کن:", reply_markup=buy_menu_keyboard()
        )

    elif data == "buy_volume":
        await query.edit_message_text(
            "یکی از پلن‌های حجمی رو انتخاب کن:",
            reply_markup=plans_keyboard(VOLUME_PLANS, "vol"),
        )

    elif data == "buy_time":
        await query.edit_message_text(
            "یکی از پلن‌های زمانی رو انتخاب کن:",
            reply_markup=plans_keyboard(TIME_PLANS, "time"),
        )

    elif data.startswith("vol_") or data.startswith("time_"):
        prefix, key = data.split("_", 1)
        plans = VOLUME_PLANS if prefix == "vol" else TIME_PLANS
        plan = plans[key]
        context.user_data["selected_plan"] = {
            "type": "حجمی" if prefix == "vol" else "زمانی",
            "label": plan["label"],
            "price": plan["price"],
        }
        context.user_data["awaiting_receipt"] = True
        text = (
            f"پلن انتخابی: {plan['label']}\n"
            f"مبلغ: {plan['price']:,} تومان\n\n"
            f"{CARD_INFO}"
        )
        await query.edit_message_text(text, reply_markup=cancel_keyboard())

    elif data == "menu_support":
        context.user_data["awaiting_support_msg"] = True
        await query.edit_message_text(
            "پیامت رو بنویس تا برای پشتیبانی ارسال بشه:",
            reply_markup=cancel_keyboard(),
        )

    elif data == "menu_guide":
        await query.edit_message_text(GUIDE_TEXT, reply_markup=back_keyboard())

    elif data == "menu_rep":
        context.user_data["awaiting_rep"] = True
        await query.edit_message_text(
            "یوزرنیم تلگرامت رو ارسال کن (مثال: @username):",
            reply_markup=cancel_keyboard(),
        )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_receipt"):
        return
    user = update.effective_user
    plan = context.user_data.get("selected_plan", {})
    photo = update.message.photo[-1]

    caption = (
        "📥 رسید جدید\n"
        f"👤 کاربر: {user.first_name} (@{user.username})\n"
        f"🆔 آیدی: {user.id}\n"
        f"📦 پلن: {plan.get('label', '-')}\n"
        f"💰 مبلغ: {plan.get('price', 0):,} تومان"
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo.file_id, caption=caption)
    await update.message.reply_text(
        "✅ رسید شما دریافت شد و برای بررسی ارسال شد. لطفاً منتظر تأیید ادمین بمان.",
        reply_markup=back_keyboard(),
    )
    context.user_data["awaiting_receipt"] = False


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if context.user_data.get("awaiting_support_msg"):
        ticket_counter["value"] += 1
        ticket_id = ticket_counter["value"]
        tickets[ticket_id] = {
            "user_id": user.id,
            "message": update.message.text,
            "date": datetime.now().isoformat(),
            "status": "open",
        }
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🎫 تیکت #{ticket_id}\n"
                f"👤 {user.first_name} (@{user.username})\n"
                f"🆔 {user.id}\n\n"
                f"{update.message.text}\n\n"
                f"پاسخ: /reply {user.id} متن پاسخ"
            ),
        )
        await update.message.reply_text(
            f"✅ پیام شما ثبت شد. شماره پیگیری: #{ticket_id}",
            reply_markup=back_keyboard(),
        )
        context.user_data["awaiting_support_msg"] = False
        return

    if context.user_data.get("awaiting_rep"):
        pending_reps[user.id] = update.message.text
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🟣 درخواست نمایندگی جدید\n"
                f"👤 {user.first_name}\n"
                f"🆔 {user.id}\n"
                f"یوزرنیم: {update.message.text}"
            ),
        )
        await update.message.reply_text(
            "✅ درخواست نمایندگی شما ثبت شد.", reply_markup=back_keyboard()
        )
        context.user_data["awaiting_rep"] = False
        return


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("فرمت درست: /reply USER_ID متن پاسخ")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("آیدی کاربر باید عدد باشه.")
        return
    reply_text = " ".join(context.args[1:])
    try:
        await context.bot.send_message(
            chat_id=target_id, text=f"📩 پاسخ پشتیبانی:\n\n{reply_text}"
        )
        await update.message.reply_text("✅ پاسخ ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ ارسال پیام ناموفق بود: {e}")


# ---------- Flask فقط برای Health Check ----------
flask_app = Flask(__name__)


@flask_app.route("/")
def health():
    return "OK", 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("متغیر محیطی BOT_TOKEN تنظیم نشده است.")

    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("ربات با موفقیت استارت شد (Polling)...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
