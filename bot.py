# ============================================
# ربات تلگرام فروش کانفیگ
# با python-telegram-bot==20.6 و Flask==2.3.3
# استایل: Functional + async/await
# دیتابیس: JSON
# اجرا: Polling + Thread برای Flask
# ============================================

import os
import sys
import json
import logging
import threading
import time
from datetime import datetime
from dotenv import load_dotenv

# ===== کتابخانه‌های اصلی =====
from flask import Flask, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===== بارگذاری متغیرهای محیطی =====
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN تنظیم نشده!")
    sys.exit(1)

# ===== تنظیمات لاگ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ===== دیتابیس JSON =====
DATA_FILE = "users_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ===== قیمت‌ها (قابل تغییر) =====
PRICES = {
    "5gb": 5000,
    "10gb": 8000,
    "20gb": 14000,
    "50gb": 30000,
    "1month": 15000,
    "3month": 40000,
    "6month": 70000,
    "1year": 120000,
}

VOLUME_BUTTONS = [
    ("🔵 ۵ گیگ", "5gb"),
    ("🟢 ۱۰ گیگ", "10gb"),
    ("🔴 ۲۰ گیگ", "20gb"),
    ("🟣 ۵۰ گیگ", "50gb"),
]

TIME_BUTTONS = [
    ("🔵 ۱ ماهه", "1month"),
    ("🟢 ۳ ماهه", "3month"),
    ("🔴 ۶ ماهه", "6month"),
    ("🟣 ۱ ساله", "1year"),
]

# ============================================
# کیبوردها
# ============================================

def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["📌 خرید اشتراک", "🟢 پشتیبانی"],
        ["📖 آموزش", "🟣 درخواست نمایندگی"]
    ], resize_keyboard=True)

def get_purchase_keyboard():
    return ReplyKeyboardMarkup([
        ["🔵 اشتراک حجمی", "🟢 اشتراک زمانی"],
        ["🔴 بازگشت"]
    ], resize_keyboard=True)

def get_volume_keyboard():
    buttons = []
    row = []
    for label, key in VOLUME_BUTTONS:
        price = PRICES[key]
        row.append(KeyboardButton(f"{label} - {price:,} تومان"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(["🔴 بازگشت"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_time_keyboard():
    buttons = []
    row = []
    for label, key in TIME_BUTTONS:
        price = PRICES[key]
        row.append(KeyboardButton(f"{label} - {price:,} تومان"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(["🔴 بازگشت"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_payment_keyboard():
    return ReplyKeyboardMarkup([
        ["📸 ارسال رسید"],
        ["🔴 بازگشت"]
    ], resize_keyboard=True)

# ============================================
# هندلرهای ربات
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or "ندارد"
    
    # ذخیره کاربر
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "username": username,
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "subscription": None,
            "tickets": [],
            "receipts": []
        }
        save_data(data)
        logger.info(f"✅ کاربر جدید: {username} ({user_id})")
    
    data[user_id]["last_active"] = datetime.now().isoformat()
    save_data(data)
    
    welcome_text = (
        "🏠 به ربات فروش کانفیگ خوش آمدید!\n\n"
        "📌 برای خرید اشتراک، دریافت آموزش، "
        "ارتباط با پشتیبانی یا ثبت درخواست نمایندگی، "
        "از دکمه‌های زیر استفاده کنید.\n\n"
        "⚡ سریع و آسان!"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text
    user = message.from_user
    user_id = str(user.id)
    
    # ===== پردازش عکس رسید =====
    if message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        
        data = load_data()
        user_choice = data.get(user_id, {}).get("last_choice", {})
        
        # ارسال به ادمین
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=(
                f"💰 رسید پرداخت جدید:\n\n"
                f"👤 کاربر: @{user.username or 'ندارد'}\n"
                f"🆔 آیدی: {user.id}\n"
                f"📦 اشتراک: {user_choice.get('label', 'نامشخص')}\n"
                f"💰 مبلغ: {user_choice.get('price', 0):,} تومان\n"
                f"📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"⏳ در انتظار تایید..."
            )
        )
        
        # ذخیره رسید
        if user_id in data:
            if "receipts" not in data[user_id]:
                data[user_id]["receipts"] = []
            data[user_id]["receipts"].append({
                "date": datetime.now().isoformat(),
                "subscription": user_choice.get("label", "نامشخص"),
                "price": user_choice.get("price", 0),
                "status": "pending"
            })
            save_data(data)
        
        await message.reply_text(
            f"✅ رسید شما با موفقیت دریافت شد.\n\n"
            f"💰 مبلغ: {user_choice.get('price', 0):,} تومان\n"
            f"📦 اشتراک: {user_choice.get('label', 'نامشخص')}\n\n"
            f"⏳ در حال بررسی توسط ادمین...\n"
            f"🔹 ظرف ۵-۱۰ دقیقه تایید و کانفیگ رو دریافت میکنید.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # ===== پردازش خرید حجمی =====
    for label, key in VOLUME_BUTTONS:
        price = PRICES[key]
        if text == f"{label} - {price:,} تومان":
            user_choice = {"type": "volume", "key": key, "label": label, "price": price}
            data = load_data()
            if user_id in data:
                data[user_id]["last_choice"] = user_choice
                save_data(data)
            
            await show_payment_page(update, user_choice)
            return
    
    # ===== پردازش خرید زمانی =====
    for label, key in TIME_BUTTONS:
        price = PRICES[key]
        if text == f"{label} - {price:,} تومان":
            user_choice = {"type": "time", "key": key, "label": label, "price": price}
            data = load_data()
            if user_id in data:
                data[user_id]["last_choice"] = user_choice
                save_data(data)
            
            await show_payment_page(update, user_choice)
            return
    
    # ===== دکمه‌های منو =====
    if text == "📌 خرید اشتراک":
        await message.reply_text("🛒 نوع اشتراک را انتخاب کنید:", reply_markup=get_purchase_keyboard())
    
    elif text == "🔵 اشتراک حجمی":
        await message.reply_text("📦 انتخاب حجم اشتراک:", reply_markup=get_volume_keyboard())
    
    elif text == "🟢 اشتراک زمانی":
        await message.reply_text("⏰ انتخاب مدت زمان اشتراک:", reply_markup=get_time_keyboard())
    
    elif text == "📸 ارسال رسید":
        await message.reply_text(
            "📸 لطفاً تصویر رسید یا کد پیگیری رو ارسال کنید:\n\n"
            "می‌تونید:\n"
            "• عکس از فیش واریزی\n"
            "• یا کد پیگیری رو به صورت متن بفرستید\n\n"
            "⚠️ حتماً مبلغ دقیق رو واریز کنید.",
            reply_markup=ReplyKeyboardMarkup([["🔴 انصراف"]], resize_keyboard=True)
        )
    
    elif text == "🟢 پشتیبانی":
        await message.reply_text(
            "✏️ لطفاً پیام خود را بنویسید:\n\n"
            "📌 نکات:\n"
            "• مشکل خود را دقیق شرح دهید\n"
            "• اگر خطایی دریافت کردید، اسکرین‌شات بفرستید",
            reply_markup=ReplyKeyboardMarkup([["🔴 بازگشت"]], resize_keyboard=True)
        )
    
    elif text == "📖 آموزش":
        await message.reply_text(
            "📖 آموزش اتصال به کانفیگ:\n\n"
            "۱️⃣ فایل کانفیگ دریافتی را ذخیره کنید\n"
            "۲️⃣ اپلیکیشن مورد نظر را اجرا کنید\n"
            "۳️⃣ گزینه Import Config را انتخاب کنید\n"
            "۴️⃣ فایل کانفیگ را انتخاب کنید\n"
            "۵️⃣ دکمه Connect را بزنید\n\n"
            "⚠️ نکات مهم:\n"
            "• حتماً اینترنت خود را بررسی کنید\n"
            "• در صورت مشکل، اپلیکیشن را ریستارت کنید\n"
            "• اگر ارور داد، از پشتیبانی کمک بگیرید",
            reply_markup=ReplyKeyboardMarkup([["🔴 بازگشت"]], resize_keyboard=True)
        )
    
    elif text == "🟣 درخواست نمایندگی":
        await message.reply_text(
            "🤝 ثبت درخواست نمایندگی:\n\n"
            "برای ثبت درخواست، لطفاً **یوزرنیم** خود را ارسال کنید:\n"
            "مثال: @your_username\n\n"
            "📋 شرایط:\n"
            "• حداقل ۲۰ مشتری فعال\n"
            "• داشتن کانال تلگرامی\n"
            "• آشنایی با کانفیگ‌ها",
            reply_markup=ReplyKeyboardMarkup([["🔴 بازگشت"]], resize_keyboard=True)
        )
    
    elif text == "🔴 بازگشت":
        await message.reply_text("🏠 منوی اصلی:", reply_markup=get_main_keyboard())
    
    elif text == "🔴 انصراف":
        await message.reply_text("✅ انصراف انجام شد.", reply_markup=get_main_keyboard())
    
    else:
        # ===== ارسال پیام متنی به ادمین =====
        if user.id != ADMIN_ID:
            # ذخیره تیکت
            data = load_data()
            if user_id in data:
                if "tickets" not in data[user_id]:
                    data[user_id]["tickets"] = []
                ticket_id = len(data[user_id]["tickets"]) + 1
                data[user_id]["tickets"].append({
                    "id": ticket_id,
                    "message": text,
                    "date": datetime.now().isoformat(),
                    "status": "open"
                })
                save_data(data)
            
            # ارسال به ادمین
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"📩 پیام جدید از کاربر:\n\n"
                    f"👤 کاربر: @{user.username or 'ندارد'}\n"
                    f"🆔 آیدی: {user.id}\n"
                    f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"📝 متن پیام:\n{text}\n\n"
                    f"💡 برای پاسخ: /reply {user.id} [متن پاسخ]"
                )
            )
            
            await message.reply_text(
                f"✅ پیام شما با موفقیت به پشتیبان ارسال شد.\n\n"
                f"📌 شماره پیگیری: #TICKET-{str(user.id)[-4:]}\n"
                f"⏳ در اسرع وقت پاسخ داده میشه.",
                reply_markup=get_main_keyboard()
            )
        else:
            # ===== دستورات ادمین =====
            if text.startswith("/reply "):
                parts = text.split(" ", 2)
                if len(parts) >= 3:
                    target_user_id = parts[1]
                    reply_text = parts[2]
                    try:
                        await context.bot.send_message(
                            chat_id=int(target_user_id),
                            text=f"📩 پاسخ از پشتیبان:\n\n{reply_text}"
                        )
                        await message.reply_text("✅ پاسخ شما با موفقیت ارسال شد.")
                    except Exception as e:
                        await message.reply_text(f"❌ خطا: {e}")
            else:
                await message.reply_text(
                    "⚠️ دستور نامعتبر!\n"
                    "/reply [USER_ID] [متن پاسخ]"
                )

async def show_payment_page(update: Update, choice: dict):
    payment_text = (
        f"💳 تکمیل خرید:\n\n"
        f"📦 اشتراک: {choice['label']}\n"
        f"💰 مبلغ: {choice['price']:,} تومان\n\n"
        f"🏦 اطلاعات واریز:\n"
        f"شماره کارت: **6037-9912-3456-7890**\n"
        f"به نام: [نام صاحب حساب]\n"
        f"بانک: [نام بانک]\n\n"
        f"📌 مراحل:\n"
        f"1️⃣ مبلغ دقیق رو به کارت بالا واریز کنید\n"
        f"2️⃣ رسید رو در همین صفحه ارسال کنید\n"
        f"3️⃣ ظرف چند دقیقه تایید و کانفیگ رو دریافت میکنید"
    )
    
    await update.message.reply_text(payment_text, reply_markup=get_payment_keyboard())

# ============================================
# Flask (فقط برای Health Check)
# ============================================

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Bot is running with Polling!", 200

@flask_app.route('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200

def run_flask():
    try:
        logger.info(f"🔥 Flask در حال اجرا روی پورت {PORT} (برای Health Check)")
        flask_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ خطای Flask: {e}")

# ============================================
# تابع اصلی
# ============================================

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask thread شروع شد")
    
    logger.info("🤖 ربات شروع به کار کرد (Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 برنامه با Ctrl+C متوقف شد")
    except Exception as e:
        logger.error(f"❌ خطای اجرا: {e}")
        time.sleep(5)
        os.execv(sys.executable, ['python'] + sys.argv)
