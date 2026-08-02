import asyncio
import logging
import os
import sys
import signal
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request, jsonify
import threading
import time

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

# ===== متغیرهای محیطی =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # اختیاری

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN تنظیم نشده!")
    sys.exit(1)

if not WEBHOOK_URL:
    logger.error("❌ WEBHOOK_URL تنظیم نشده!")
    sys.exit(1)

# ===== تنظیمات قیمت‌ها (قابل تغییر) =====
PRICES = {
    # اشتراک حجمی
    "5gb": 5000,
    "10gb": 8000,
    "20gb": 14000,
    "50gb": 30000,
    
    # اشتراک زمانی
    "1month": 15000,
    "3month": 40000,
    "6month": 70000,
    "1year": 120000,
}

# ===== تنظیمات دکمه‌ها =====
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

# ===== دیتابیس ساده (فایل JSON) =====
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

# ===== راه‌اندازی Flask =====
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Bot is running!", 200

@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        update_data = await request.get_json()
        update = types.Update(**update_data)
        await dp.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"❌ خطا در webhook: {e}")
        return "ERROR", 500

@flask_app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"❌ خطای Flask: {e}")
    return "Internal Server Error", 500

# ===== راه‌اندازی ربات =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== ساخت کیبوردها =====

# 1. کیبورد اصلی
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📌 خرید اشتراک"),
                KeyboardButton(text="🟢 پشتیبانی")
            ],
            [
                KeyboardButton(text="📖 آموزش"),
                KeyboardButton(text="🟣 درخواست نمایندگی")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

# 2. کیبورد خرید اشتراک
def get_purchase_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔵 اشتراک حجمی"),
                KeyboardButton(text="🟢 اشتراک زمانی")
            ],
            [
                KeyboardButton(text="🔴 بازگشت")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

# 3. کیبورد اشتراک حجمی
def get_volume_keyboard():
    buttons = []
    row = []
    for i, (label, key) in enumerate(VOLUME_BUTTONS):
        price = PRICES[key]
        button_text = f"{label} - {price:,} تومان"
        row.append(KeyboardButton(text=button_text))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([KeyboardButton(text="🔴 بازگشت")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

# 4. کیبورد اشتراک زمانی
def get_time_keyboard():
    buttons = []
    row = []
    for i, (label, key) in enumerate(TIME_BUTTONS):
        price = PRICES[key]
        button_text = f"{label} - {price:,} تومان"
        row.append(KeyboardButton(text=button_text))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([KeyboardButton(text="🔴 بازگشت")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

# 5. کیبورد پرداخت
def get_payment_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 ارسال رسید")],
            [KeyboardButton(text="🔴 بازگشت")]
        ],
        resize_keyboard=True
    )
    return keyboard

# 6. کیبورد پشتیبانی
def get_support_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 ارسال پیام")],
            [KeyboardButton(text="🔴 بازگشت")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ===== هندلرهای ربات =====

@dp.message(Command("start"))
async def start_command(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        username = message.from_user.username or "ندارد"
        
        # ذخیره کاربر در دیتابیس
        data = load_data()
        if user_id not in data:
            data[user_id] = {
                "username": username,
                "first_seen": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "subscription": None,
                "tickets": []
            }
            save_data(data)
            logger.info(f"✅ کاربر جدید: {username} ({user_id})")
        
        # بروزرسانی آخرین فعالیت
        data[user_id]["last_active"] = datetime.now().isoformat()
        save_data(data)
        
        # چک کردن عضویت در کانال (اختیاری)
        if CHANNEL_ID:
            try:
                member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=message.from_user.id)
                if member.status in ['left', 'kicked']:
                    await message.answer(
                        f"📢 لطفاً ابتدا در کانال زیر عضو شوید:\n\n"
                        f"🔗 {CHANNEL_ID}\n\n"
                        f"✅ بعد از عضویت، دکمه «بررسی عضویت» رو بزنید",
                        reply_markup=ReplyKeyboardMarkup(
                            keyboard=[[KeyboardButton(text="✅ بررسی عضویت")]],
                            resize_keyboard=True
                        )
                    )
                    return
            except Exception as e:
                logger.warning(f"⚠️ خطا در چک عضویت: {e}")
        
        # پیام خوش‌آمدگویی
        welcome_text = (
            "🏠 به ربات فروش کانفیگ خوش آمدید!\n\n"
            "📌 برای خرید اشتراک، دریافت آموزش، ارتباط با پشتیبانی یا ثبت درخواست نمایندگی، "
            "از دکمه‌های زیر استفاده کنید.\n\n"
            "⚡ سریع و آسان!"
        )
        
        await message.answer(welcome_text, reply_markup=get_main_keyboard())
        
    except Exception as e:
        logger.error(f"❌ خطا در start: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

@dp.message(lambda message: message.text == "✅ بررسی عضویت")
async def check_membership(message: types.Message):
    try:
        if not CHANNEL_ID:
            await message.answer("⚠️ کانالی تنظیم نشده است!", reply_markup=get_main_keyboard())
            return
        
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=message.from_user.id)
        if member.status in ['left', 'kicked']:
            await message.answer(
                "❌ شما هنوز عضو کانال نشده‌اید!\n"
                f"🔗 لطفاً عضو شوید: {CHANNEL_ID}",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="✅ بررسی مجدد")]],
                    resize_keyboard=True
                )
            )
        else:
            await message.answer(
                "✅ عضویت شما تأیید شد!",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        logger.error(f"❌ خطا در بررسی عضویت: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

@dp.message(lambda message: message.text == "✅ بررسی مجدد")
async def recheck_membership(message: types.Message):
    await check_membership(message)

@dp.message(lambda message: message.text == "📌 خرید اشتراک")
async def purchase_menu(message: types.Message):
    try:
        await message.answer(
            "🛒 نوع اشتراک را انتخاب کنید:",
            reply_markup=get_purchase_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ خطا در خرید: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

@dp.message(lambda message: message.text == "🔵 اشتراک حجمی")
async def volume_subscription(message: types.Message):
    try:
        await message.answer(
            "📦 انتخاب حجم اشتراک:\n\n"
            "📌 قیمت‌ها روی دکمه‌ها نمایش داده شده‌اند.",
            reply_markup=get_volume_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ خطا در حجمی: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

@dp.message(lambda message: message.text == "🟢 اشتراک زمانی")
async def time_subscription(message: types.Message):
    try:
        await message.answer(
            "⏰ انتخاب مدت زمان اشتراک:\n\n"
            "📌 قیمت‌ها روی دکمه‌ها نمایش داده شده‌اند.",
            reply_markup=get_time_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ خطا در زمانی: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

@dp.message()
async def handle_all_messages(message: types.Message):
    try:
        text = message.text
        
        # ===== پردازش عکس رسید =====
        if message.photo:
            # دریافت عکس رسید
            photo = message.photo[-1]
            file_id = photo.file_id
            
            # دریافت اطلاعات کاربر از دیتابیس
            data = load_data()
            user_id = str(message.from_user.id)
            user_choice = data.get(user_id, {}).get("last_choice", {})
            
            # ارسال به ادمین
            await bot.send_photo(
                ADMIN_ID,
                photo=file_id,
                caption=(
                    f"💰 رسید پرداخت جدید:\n\n"
                    f"👤 کاربر: @{message.from_user.username or 'ندارد'}\n"
                    f"🆔 آیدی: {message.from_user.id}\n"
                    f"📦 اشتراک: {user_choice.get('label', 'نامشخص')}\n"
                    f"💰 مبلغ: {user_choice.get('price', 0):,} تومان\n"
                    f"📅 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"⏳ در انتظار تایید..."
                )
            )
            
            # ذخیره در دیتابیس
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
            
            # پیام موفقیت به کاربر
            await message.answer(
                "✅ رسید شما با موفقیت دریافت شد.\n\n"
                "💰 مبلغ: {:,} تومان\n"
                "📦 اشتراک: {}\n\n"
                "⏳ در حال بررسی توسط ادمین...\n"
                "🔹 ظرف ۵-۱۰ دقیقه تایید و کانفیگ رو دریافت میکنید.\n\n"
                "⚠️ لطفاً منتظر بمونید و پیام جدید ارسال نکنید.".format(
                    user_choice.get('price', 0),
                    user_choice.get('label', 'نامشخص')
                ),
                reply_markup=get_main_keyboard()
            )
            return
        
        # ===== پردازش خرید اشتراک حجمی =====
        for label, key in VOLUME_BUTTONS:
            price = PRICES[key]
            if text == f"{label} - {price:,} تومان":
                user_choice = {
                    "type": "volume",
                    "key": key,
                    "label": label,
                    "price": price
                }
                # ذخیره در دیتابیس
                data = load_data()
                user_id = str(message.from_user.id)
                if user_id in data:
                    data[user_id]["last_choice"] = user_choice
                    save_data(data)
                
                await show_payment_page(message, user_choice)
                return
        
        # ===== پردازش خرید اشتراک زمانی =====
        for label, key in TIME_BUTTONS:
            price = PRICES[key]
            if text == f"{label} - {price:,} تومان":
                user_choice = {
                    "type": "time",
                    "key": key,
                    "label": label,
                    "price": price
                }
                data = load_data()
                user_id = str(message.from_user.id)
                if user_id in data:
                    data[user_id]["last_choice"] = user_choice
                    save_data(data)
                
                await show_payment_page(message, user_choice)
                return
        
        # ===== پردازش دکمه‌های دیگر =====
        if text == "📸 ارسال رسید":
            await message.answer(
                "📸 لطفاً تصویر رسید یا کد پیگیری رو ارسال کنید:\n\n"
                "می‌تونید:\n"
                "• عکس از فیش واریزی\n"
                "• یا کد پیگیری رو به صورت متن بفرستید\n\n"
                "⚠️ حتماً مبلغ دقیق رو واریز کنید.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="🔴 انصراف")]],
                    resize_keyboard=True
                )
            )
        
        elif text == "🟢 پشتیبانی":
            await message.answer(
                "✏️ لطفاً پیام خود را بنویسید:\n\n"
                "📌 نکات:\n"
                "• مشکل خود را دقیق شرح دهید\n"
                "• اگر خطایی دریافت کردید، اسکرین‌شات بفرستید\n"
                "• کانفیگ خریداری‌شده را ذکر کنید",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="🔴 بازگشت")]],
                    resize_keyboard=True
                )
            )
        
        elif text == "📤 ارسال پیام":
            await message.answer(
                "✏️ لطفاً متن پیام خود را بنویسید:"
            )
        
        elif text == "📖 آموزش":
            await message.answer(
                "📖 آموزش اتصال به کانفیگ:\n\n"
                "۱️⃣ فایل کانفیگ دریافتی را در پوشه مشخصی ذخیره کنید\n"
                "۲️⃣ اپلیکیشن مورد نظر (مثلاً V2RayNG) را اجرا کنید\n"
                "۳️⃣ گزینه Import Config یا + را انتخاب کنید\n"
                "۴️⃣ فایل کانفیگ را از پوشه انتخاب کنید\n"
                "۵️⃣ دکمه Connect یا اتصال را بزنید\n\n"
                "⚠️ نکات مهم:\n"
                "• حتماً اینترنت خود را بررسی کنید\n"
                "• در صورت مشکل، اپلیکیشن را ریستارت کنید\n"
                "• اگر ارور داد، از پشتیبانی کمک بگیرید",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="🔴 بازگشت")]],
                    resize_keyboard=True
                )
            )
        
        elif text == "🟣 درخواست نمایندگی":
            await message.answer(
                "🤝 ثبت درخواست نمایندگی:\n\n"
                "برای ثبت درخواست، لطفاً **یوزرنیم** خود را ارسال کنید:\n"
                "مثال: @your_username\n\n"
                "📋 شرایط:\n"
                "• حداقل ۲۰ مشتری فعال\n"
                "• داشتن کانال تلگرامی\n"
                "• آشنایی با کانفیگ‌ها",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="🔴 بازگشت")]],
                    resize_keyboard=True
                )
            )
        
        elif text == "🔴 بازگشت":
            await message.answer(
                "🏠 منوی اصلی:",
                reply_markup=get_main_keyboard()
            )
        
        elif text == "🔴 انصراف":
            await message.answer(
                "✅ انصراف انجام شد.",
                reply_markup=get_main_keyboard()
            )
        
        else:
            # ===== پردازش پیام متنی کاربر =====
            if message.from_user.id != ADMIN_ID:
                # ذخیره پیام در دیتابیس
                data = load_data()
                user_id = str(message.from_user.id)
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
                await bot.send_message(
                    ADMIN_ID,
                    f"📩 پیام جدید از کاربر:\n\n"
                    f"👤 کاربر: @{message.from_user.username or 'ندارد'}\n"
                    f"🆔 آیدی: {message.from_user.id}\n"
                    f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"📝 متن پیام:\n{text}\n\n"
                    f"💡 برای پاسخ: /reply {message.from_user.id} [متن پاسخ]"
                )
                
                # پیام موفقیت به کاربر
                await message.answer(
                    "✅ پیام شما با موفقیت به پشتیبان ارسال شد.\n\n"
                    f"📌 شماره پیگیری: #TICKET-{str(message.from_user.id)[-4:]}\n"
                    "⏳ در اسرع وقت پاسخ داده میشه (حداکثر ۲۴ ساعت).",
                    reply_markup=get_main_keyboard()
                )
            else:
                # ===== دستورات ادمین =====
                if text.startswith("/reply "):
                    parts = text.split(" ", 2)
                    if len(parts) >= 3:
                        user_id = parts[1]
                        reply_text = parts[2]
                        try:
                            # ارسال پاسخ به کاربر
                            await bot.send_message(
                                int(user_id),
                                f"📩 پاسخ از پشتیبان:\n\n{reply_text}"
                            )
                            await message.answer("✅ پاسخ شما با موفقیت ارسال شد.")
                            
                            # ذخیره در دیتابیس
                            data = load_data()
                            if user_id in data:
                                if "tickets" in data[user_id]:
                                    for ticket in data[user_id]["tickets"]:
                                        if ticket["status"] == "open":
                                            ticket["status"] = "closed"
                                            break
                                save_data(data)
                                
                        except Exception as e:
                            await message.answer(f"❌ خطا در ارسال پاسخ: {e}")
                    else:
                        await message.answer(
                            "⚠️ فرمت صحیح:\n"
                            "/reply [USER_ID] [متن پاسخ]"
                        )
                else:
                    await message.answer(
                        "⚠️ دستور نامعتبر!\n"
                        "برای پاسخ به کاربر از دستور زیر استفاده کنید:\n"
                        "/reply [USER_ID] [متن پاسخ]"
                    )
    
    except Exception as e:
        logger.error(f"❌ خطا در پردازش پیام: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

# ===== صفحه پرداخت =====
async def show_payment_page(message: types.Message, choice: dict):
    try:
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
        
        await message.answer(payment_text, reply_markup=get_payment_keyboard())
    except Exception as e:
        logger.error(f"❌ خطا در نمایش پرداخت: {e}")
        await message.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.")

# ===== تابع راه‌اندازی Flask =====
def run_flask():
    try:
        logger.info(f"🔥 Flask در حال اجرا روی پورت {PORT}")
        flask_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ خطای Flask: {e}")

# ===== تابع تنظیم Webhook =====
async def set_webhook():
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"✅ Webhook تنظیم شد: {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در تنظیم Webhook: {e}")
        return False

# ===== تابع اصلی =====
async def main():
    # تنظیم Webhook
    webhook_set = await set_webhook()
    if not webhook_set:
        logger.warning("⚠️ Webhook تنظیم نشد، تلاش مجدد...")
        for i in range(5):
            await asyncio.sleep(5)
            if await set_webhook():
                break
    
    # شروع Flask در یک ترد جداگانه
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask thread شروع شد")
    
    # ===== مدیریت سیگنال‌ها =====
    def signal_handler(sig, frame):
        logger.info("🛑 سیگنال دریافت شد، در حال خروج...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # ===== حلقه اصلی =====
    logger.info("🤖 ربات شروع به کار کرد!")
    
    try:
        while True:
            await asyncio.sleep(60)
            
            # چک کردن سلامت Webhook
            try:
                webhook_info = await bot.get_webhook_info()
                expected_url = f"{WEBHOOK_URL}/webhook"
                if webhook_info.url != expected_url:
                    logger.warning("⚠️ Webhook تغییر کرده، تنظیم مجدد...")
                    await set_webhook()
            except Exception as e:
                logger.error(f"❌ خطا در چک Webhook: {e}")
                await asyncio.sleep(5)
                await set_webhook()
            
            # گزارش وضعیت هر ۵ دقیقه
            if datetime.now().minute % 5 == 0:
                logger.info("✅ ربات سالم است")
                
    except Exception as e:
        logger.error(f"❌ خطای اصلی: {e}")
        await asyncio.sleep(5)
        # ری‌استارت خودکار
        os.execv(sys.executable, ['python'] + sys.argv)

# ===== اجرای برنامه =====
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 برنامه با Ctrl+C متوقف شد")
    except Exception as e:
        logger.error(f"❌ خطای اجرا: {e}")
        time.sleep(5)
        # ری‌استارت خودکار
        os.execv(sys.executable, ['python'] + sys.argv)
