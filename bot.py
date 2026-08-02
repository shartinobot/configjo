"""
ربات تلگرام فروش کانفیگ (VPN/پروکسی)
نسخه کامل با پشتیبانی از خرید اشتراک، پشتیبانی، آموزش و نمایندگی
قابل اجرا روی Render با Flask Web Server
"""

import os
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple
from threading import Thread
from flask import Flask, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------- تنظیمات اولیه --------------------
# دریافت توکن از متغیرهای محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("توکن ربات پیدا نشد! لطفاً متغیر محیطی BOT_TOKEN را تنظیم کنید.")

ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID تنظیم نشده است!")

CHANNEL_ID = os.environ.get("CHANNEL_ID")  # اختیاری

# فعال کردن لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- دیتابیس JSON --------------------
USERS_FILE = "users_data.json"

def load_users() -> Dict:
    """بارگذاری اطلاعات کاربران از فایل"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users: Dict):
    """ذخیره اطلاعات کاربران در فایل"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user(user_id: int) -> Dict:
    """دریافت اطلاعات یک کاربر"""
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": "",
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "subscription": None,
            "last_choice": {},
            "tickets": [],
            "receipts": [],
            "pending_payment": None
        }
        save_users(users)
    return users[str(user_id)]

def update_user(user_id: int, data: Dict):
    """به‌روزرسانی اطلاعات کاربر"""
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {}
    users[str(user_id)].update(data)
    save_users(users)

# -------------------- قیمت‌ها --------------------
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

# اطلاعات بانکی
BANK_INFO = {
    "card_number": "6037-9975-1234-5678",
    "account_name": "علی رضایی",
    "bank_name": "بانک ملی"
}

# -------------------- توابع کمکی --------------------
def generate_ticket_id() -> int:
    """تولید شماره تیکت جدید"""
    return int(datetime.now().timestamp()) % 1000000

def format_date(date_str: str) -> str:
    """فرمت تاریخ"""
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y/%m/%d %H:%M")
    except:
        return date_str

# -------------------- منوی اصلی --------------------
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی اصلی"""
    keyboard = [
        [InlineKeyboardButton("📌 خرید اشتراک", callback_data="buy")],
        [InlineKeyboardButton("🟢 پشتیبانی", callback_data="support")],
        [InlineKeyboardButton("📖 آموزش", callback_data="guide")],
        [InlineKeyboardButton("🟣 درخواست نمایندگی", callback_data="agency")],
    ]
    await update.callback_query.edit_message_text(
        "🤖 به ربات فروش کانفیگ خوش آمدید!\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -------------------- دستور /start --------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر دستور /start"""
    user = update.effective_user
    user_id = user.id
    
    # ثبت کاربر
    user_data = get_user(user_id)
    user_data["username"] = user.username or ""
    user_data["last_active"] = datetime.now().isoformat()
    update_user(user_id, user_data)
    
    keyboard = [
        [InlineKeyboardButton("📌 خرید اشتراک", callback_data="buy")],
        [InlineKeyboardButton("🟢 پشتیبانی", callback_data="support")],
        [InlineKeyboardButton("📖 آموزش", callback_data="guide")],
        [InlineKeyboardButton("🟣 درخواست نمایندگی", callback_data="agency")],
    ]
    
    await update.message.reply_text(
        "🤖 به ربات فروش کانفیگ خوش آمدید!\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -------------------- خرید اشتراک --------------------
async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی خرید اشتراک"""
    keyboard = [
        [InlineKeyboardButton("🔵 اشتراک حجمی", callback_data="buy_volume")],
        [InlineKeyboardButton("🟢 اشتراک زمانی", callback_data="buy_time")],
        [InlineKeyboardButton("🔴 بازگشت", callback_data="main")],
    ]
    await update.callback_query.edit_message_text(
        "📌 **خرید اشتراک**\n\n"
        "نوع اشتراک مورد نظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def buy_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش اشتراک‌های حجمی"""
    keyboard = []
    for key, plan in VOLUME_PLANS.items():
        keyboard.append([InlineKeyboardButton(
            f"{plan['label']} - {plan['price']:,} تومان",
            callback_data=f"select_volume_{key}"
        )])
    keyboard.append([InlineKeyboardButton("🔴 بازگشت", callback_data="buy")])
    
    await update.callback_query.edit_message_text(
        "📊 **اشتراک حجمی**\n\n"
        "یکی از حجم‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def buy_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش اشتراک‌های زمانی"""
    keyboard = []
    for key, plan in TIME_PLANS.items():
        keyboard.append([InlineKeyboardButton(
            f"{plan['label']} - {plan['price']:,} تومان",
            callback_data=f"select_time_{key}"
        )])
    keyboard.append([InlineKeyboardButton("🔴 بازگشت", callback_data="buy")])
    
    await update.callback_query.edit_message_text(
        "📅 **اشتراک زمانی**\n\n"
        "یکی از بازه‌های زمانی زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب پلن و نمایش اطلاعات پرداخت"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # تشخیص نوع و کلید پلن
    if data.startswith("select_volume_"):
        plan_key = data.replace("select_volume_", "")
        plan = VOLUME_PLANS[plan_key]
        plan_type = "حجمی"
    elif data.startswith("select_time_"):
        plan_key = data.replace("select_time_", "")
        plan = TIME_PLANS[plan_key]
        plan_type = "زمانی"
    else:
        return
    
    # ذخیره انتخاب کاربر
    user_data = get_user(user_id)
    user_data["last_choice"] = {
        "type": plan_type,
        "key": plan_key,
        "label": plan["label"],
        "price": plan["price"]
    }
    user_data["pending_payment"] = {
        "plan_type": plan_type,
        "plan_key": plan_key,
        "price": plan["price"],
        "date": datetime.now().isoformat()
    }
    update_user(user_id, user_data)
    
    # نمایش اطلاعات پرداخت
    keyboard = [
        [InlineKeyboardButton("📸 ارسال رسید", callback_data="send_receipt")],
        [InlineKeyboardButton("🔴 بازگشت", callback_data="buy")],
    ]
    
    await query.edit_message_text(
        f"💰 **تایید و پرداخت**\n\n"
        f"نوع اشتراک: {plan_type}\n"
        f"پلن: {plan['label']}\n"
        f"مبلغ: {plan['price']:,} تومان\n\n"
        f"🏦 **اطلاعات واریز:**\n"
        f"شماره کارت: `{BANK_INFO['card_number']}`\n"
        f"نام صاحب حساب: {BANK_INFO['account_name']}\n"
        f"بانک: {BANK_INFO['bank_name']}\n\n"
        f"پس از واریز، رسید را ارسال کنید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def send_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت رسید از کاربر"""
    user_id = update.effective_user.id
    
    # تنظیم state برای دریافت رسید
    context.user_data["waiting_for_receipt"] = True
    
    keyboard = [[InlineKeyboardButton("🔴 انصراف", callback_data="buy")]]
    await update.callback_query.edit_message_text(
        "📸 **ارسال رسید**\n\n"
        "لطفاً عکس رسید پرداخت خود را ارسال کنید.\n"
        "برای انصراف، دکمه زیر را بزنید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش رسید ارسال شده"""
    if not context.user_data.get("waiting_for_receipt"):
        return
    
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    
    if not user_data.get("pending_payment"):
        await update.message.reply_text("❌ خطا! لطفاً مجدداً تلاش کنید.")
        return
    
    # دریافت عکس
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # ثبت رسید
    pending = user_data["pending_payment"]
    receipt_data = {
        "id": generate_ticket_id(),
        "date": datetime.now().isoformat(),
        "subscription": pending.get("plan_key", ""),
        "price": pending.get("price", 0),
        "status": "pending",
        "photo_id": file_id
    }
    
    if "receipts" not in user_data:
        user_data["receipts"] = []
    user_data["receipts"].append(receipt_data)
    user_data["pending_payment"] = None
    update_user(user_id, user_data)
    
    # ارسال به ادمین
    await send_to_admin(
        update,
        f"💰 **رسید جدید**\n\n"
        f"کاربر: @{update.effective_user.username or 'بدون نام'}\n"
        f"آیدی: `{user_id}`\n"
        f"اشتراک: {pending.get('plan_key', 'نامشخص')}\n"
        f"مبلغ: {pending.get('price', 0):,} تومان\n"
        f"تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )
    
    # ارسال عکس رسید به ادمین
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id)
    
    # پیام موفقیت به کاربر
    context.user_data["waiting_for_receipt"] = False
    keyboard = [[InlineKeyboardButton("🔴 بازگشت به منو", callback_data="main")]]
    await update.message.reply_text(
        "✅ **رسید شما با موفقیت ارسال شد!**\n\n"
        "پس از تایید توسط ادمین، کانفیگ برای شما ارسال خواهد شد.\n"
        "لطفاً صبور باشید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# -------------------- پشتیبانی --------------------
async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی پشتیبانی"""
    keyboard = [
        [InlineKeyboardButton("📝 ارسال پیام", callback_data="send_ticket")],
        [InlineKeyboardButton("🔴 بازگشت", callback_data="main")],
    ]
    await update.callback_query.edit_message_text(
        "🟢 **پشتیبانی**\n\n"
        "برای ارتباط با پشتیبانی، پیام خود را ارسال کنید.\n"
        "شماره پیگیری دریافت خواهید کرد.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def send_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت پیام تیکت"""
    user_id = update.effective_user.id
    context.user_data["waiting_for_ticket"] = True
    
    keyboard = [[InlineKeyboardButton("🔴 انصراف", callback_data="support")]]
    await update.callback_query.edit_message_text(
        "📝 **ارسال تیکت**\n\n"
        "لطفاً پیام خود را بنویسید و ارسال کنید.\n"
        "پشتیبانی در اسرع وقت پاسخ خواهد داد.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش تیکت دریافتی"""
    if not context.user_data.get("waiting_for_ticket"):
        return
    
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    ticket_id = generate_ticket_id()
    ticket_text = update.message.text
    
    # ذخیره تیکت
    ticket = {
        "id": ticket_id,
        "message": ticket_text,
        "date": datetime.now().isoformat(),
        "status": "open"
    }
    if "tickets" not in user_data:
        user_data["tickets"] = []
    user_data["tickets"].append(ticket)
    update_user(user_id, user_data)
    
    # ارسال به ادمین
    await send_to_admin(
        update,
        f"🎫 **تیکت جدید**\n\n"
        f"شماره: `{ticket_id}`\n"
        f"کاربر: @{update.effective_user.username or 'بدون نام'}\n"
        f"آیدی: `{user_id}`\n"
        f"تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"
        f"📝 متن:\n{ticket_text}"
    )
    
    # پیام موفقیت به کاربر
    context.user_data["waiting_for_ticket"] = False
    keyboard = [[InlineKeyboardButton("🔴 بازگشت به منو", callback_data="main")]]
    await update.message.reply_text(
        f"✅ **تیکت شما با موفقیت ارسال شد!**\n\n"
        f"شماره پیگیری: `{ticket_id}`\n"
        f"به زودی پاسخ شما ارسال خواهد شد.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# -------------------- آموزش --------------------
async def guide_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش راهنمای آموزش"""
    keyboard = [[InlineKeyboardButton("🔴 بازگشت", callback_data="main")]]
    
    guide_text = (
        "📖 **آموزش اتصال به کانفیگ**\n\n"
        "۱️⃣ فایل کانفیگ دریافتی را ذخیره کنید\n"
        "۲️⃣ اپلیکیشن مورد نظر را اجرا کنید\n"
        "۳️⃣ گزینه Import Config را انتخاب کنید\n"
        "۴️⃣ فایل کانفیگ را انتخاب کنید\n"
        "۵️⃣ دکمه Connect را بزنید\n\n"
        "⚠️ **نکات مهم:**\n"
        "• حتماً اینترنت خود را بررسی کنید\n"
        "• در صورت مشکل، اپلیکیشن را ریستارت کنید\n"
        "• اگر ارور داد، از پشتیبانی کمک بگیرید"
    )
    
    await update.callback_query.edit_message_text(
        guide_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# -------------------- درخواست نمایندگی --------------------
async def agency_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی درخواست نمایندگی"""
    keyboard = [
        [InlineKeyboardButton("📝 ثبت درخواست", callback_data="request_agency")],
        [InlineKeyboardButton("🔴 بازگشت", callback_data="main")],
    ]
    await update.callback_query.edit_message_text(
        "🟣 **درخواست نمایندگی**\n\n"
        "برای ثبت درخواست نمایندگی، لطفاً یوزرنیم تلگرام خود را وارد کنید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def request_agency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت درخواست نمایندگی"""
    user_id = update.effective_user.id
    context.user_data["waiting_for_agency"] = True
    
    keyboard = [[InlineKeyboardButton("🔴 انصراف", callback_data="agency")]]
    await update.callback_query.edit_message_text(
        "🟣 **ثبت درخواست نمایندگی**\n\n"
        "لطفاً یوزرنیم تلگرام خود را وارد کنید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_agency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش درخواست نمایندگی"""
    if not context.user_data.get("waiting_for_agency"):
        return
    
    user_id = update.effective_user.id
    username = update.message.text.strip()
    
    # ارسال به ادمین
    await send_to_admin(
        update,
        f"🟣 **درخواست نمایندگی جدید**\n\n"
        f"کاربر: @{update.effective_user.username or 'بدون نام'}\n"
        f"آیدی: `{user_id}`\n"
        f"یوزرنیم: {username}\n"
        f"تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )
    
    # پیام موفقیت
    context.user_data["waiting_for_agency"] = False
    keyboard = [[InlineKeyboardButton("🔴 بازگشت به منو", callback_data="main")]]
    await update.message.reply_text(
        "✅ **درخواست شما با موفقیت ثبت شد!**\n\n"
        "پس از بررسی، با شما تماس گرفته خواهد شد.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# -------------------- ارسال به ادمین --------------------
async def send_to_admin(update: Update, text: str):
    """ارسال پیام به ادمین"""
    try:
        await update.effective_message.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در ارسال به ادمین: {e}")

# -------------------- پاسخ ادمین --------------------
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاسخ ادمین به کاربر"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ شما دسترسی به این دستور ندارید!")
        return
    
    # پارس کردن دستور /reply [USER_ID] [متن]
    text = update.message.text
    parts = text.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ فرمت صحیح:\n`/reply [USER_ID] [متن]`",
            parse_mode="Markdown"
        )
        return
    
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
    except ValueError:
        await update.message.reply_text("❌ USER_ID باید عددی باشد!")
        return
    
    # ارسال پاسخ به کاربر
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📩 **پاسخ پشتیبانی:**\n\n{reply_text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ پاسخ به کاربر {user_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

# -------------------- Callback Query Handler --------------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "main":
        await show_main_menu(update, context)
    elif data == "buy":
        await buy_menu(update, context)
    elif data == "buy_volume":
        await buy_volume(update, context)
    elif data == "buy_time":
        await buy_time(update, context)
    elif data.startswith("select_volume_") or data.startswith("select_time_"):
        await select_plan(update, context)
    elif data == "send_receipt":
        await send_receipt(update, context)
    elif data == "support":
        await support_menu(update, context)
    elif data == "send_ticket":
        await send_ticket(update, context)
    elif data == "guide":
        await guide_menu(update, context)
    elif data == "agency":
        await agency_menu(update, context)
    elif data == "request_agency":
        await request_agency(update, context)
    else:
        await query.edit_message_text("❌ گزینه نامعتبر!")

# -------------------- هندلر خطا --------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر خطا"""
    logger.error(f"خطا رخ داد: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید."
            )
        except:
            pass

# -------------------- Flask Web Server --------------------
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health_check():
    """مسیر Health Check برای جلوگیری از خوابیدن ربات"""
    return jsonify({
        "status": "healthy",
        "bot": "ربات فروش کانفیگ",
        "message": "ربات در حال اجراست! ✅"
    }), 200

def run_flask():
    """اجرای وب‌سرور Flask در یک ترد جداگانه"""
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# -------------------- تابع اصلی --------------------
def main() -> None:
    """تابع اصلی - راه‌اندازی ربات"""
    
    # راه‌اندازی وب‌سرور Flask
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("وب‌سرور Flask راه‌اندازی شد")
    
    # ایجاد اپلیکیشن تلگرام
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("reply", reply_to_user))
    
    # Callback Query Handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message Handlers
    application.add_handler(MessageHandler(
        filters.PHOTO & ~filters.COMMAND, 
        handle_receipt
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_ticket
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_agency
    ))
    # توجه: این هندلرها به ترتیب اولویت بررسی می‌شوند
    
    # هندلر خطا
    application.add_error_handler(error_handler)
    
    # راه‌اندازی ربات
    logger.info("ربات فروش کانفیگ راه‌اندازی شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
