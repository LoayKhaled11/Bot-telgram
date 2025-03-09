import os
import json
import logging
from datetime import time, datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, JobQueue
from dotenv import load_dotenv
import asyncio

# تحميل المتغيرات البيئية
load_dotenv()

# تهيئة logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ملف حفظ بيانات المستخدمين
USERS_FILE = "users.json"

# التوقيت المحلي (التوقيت المصري)
LOCAL_TIMEZONE = pytz.timezone('Africa/Cairo')

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as file:
            return json.load(file)
    return {}

def save_users():
    with open(USERS_FILE, "w") as file:
        json.dump(users, file, indent=4)

# تحميل بيانات المستخدمين
users = load_users()

# دالة لتحويل الوقت من 24 ساعة إلى 12 ساعة
def convert_to_12_hour_format(hour, minute):
    if hour < 12:
        period = "صباحًا"
        if hour == 0:
            hour = 12
    else:
        period = "مساءً"
        if hour > 12:
            hour -= 12
    return f"{hour}:{minute:02d} {period}"

# بدء البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    first_name = update.message.from_user.first_name

    # التحقق من الوقت الحالي
    now = datetime.now(LOCAL_TIMEZONE)
    if 5 <= now.hour < 12:  # إذا كان الوقت بين 5 صباحًا و12 ظهرًا
        greeting = f"🌞 صباح الخير، {first_name}! 🌞\n\n"
    elif 12 <= now.hour < 18:  # إذا كان الوقت بين 12 ظهرًا و6 مساءً
        greeting = f"🌤 مساء الخير، {first_name}! 🌤\n\n"
    else:  # إذا كان الوقت بين 6 مساءً و5 صباحًا
        greeting = f"🌙 مساء الخير، {first_name}! 🌙\n\n"

    # رسالة الترحيب الكاملة
    welcome_message = (
        f"{greeting}"
        "✨🎉 اهلا بيك في بوت تذكير الخير اليومي! 🎉✨\n\n"
        "تقدر تحدد وقت تذكير يومي علشان تتبرع بجنيه واحد بس ممكن يغير حياة ناس كتير! 💸❤️\n\n"
        "**روابط التبرع:**\n"
        "- 💳 [انستا باي](https://instapay.com)\n"
        "- 📱 [فودافون كاش](https://vodafonecash.com)\n\n"
        "**رقم الدعم الفني:** 0123456789\n"
        "**رقم تحصيل التبرعات:** 0111222333\n\n"
        "لو عايز تكبر دائرة الخير، شارك البوت مع أصدقائك! 🙏😊"
    )

    # إرسال رسالة الترحيب
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

    # إرسال دليل الاستخدام (صورة) إذا كانت موجودة
    if os.path.exists("guide.jpg"):
        with open("guide.jpg", "rb") as photo:
            await update.message.reply_photo(photo)
    else:
        logger.warning("ملف الصورة guide.jpg غير موجود.")

    # تهيئة المستخدم الجديد
    if user_id not in users:
        users[user_id] = {'notifications': [], 'join_date': datetime.now().strftime("%Y-%m-%d")}
    save_users()

    # إرسال رسالة لتحديد الموعد
    await update.message.reply_text("⏰ دلوقتي تقدر تحدد وقت التذكير اليومي بتاعك:")

    # عرض خيارات الساعة
    await show_hour_options(update, context)

# عرض خيارات الساعة
async def show_hour_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"hour_{i}") for i in range(1, 7)],
        [InlineKeyboardButton(str(i), callback_data=f"hour_{i}") for i in range(7, 13)],
        [InlineKeyboardButton("إلغاء المواعيد", callback_data="cancel_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⏰ اختر الساعة:", reply_markup=reply_markup)

# معالجة اختيار الساعة
async def handle_hour_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "cancel_all":
        await cancel_all_notifications(query)
        return
    hour = int(query.data.split("_")[1])
    context.user_data['hour'] = hour
    keyboard = [
        [InlineKeyboardButton("🌞 صباحًا", callback_data="period_am")],
        [InlineKeyboardButton("🌙 مساءً", callback_data="period_pm")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"⏰ اخترت الساعة {hour}. دلوقتي اختر الفترة:", reply_markup=reply_markup)

# إلغاء جميع المواعيد
async def cancel_all_notifications(query) -> None:
    user_id = str(query.from_user.id)
    if user_id in users:
        users[user_id]['notifications'] = []
        save_users()
        await query.edit_message_text("✅ تم إلغاء جميع المواعيد السابقة.")
    else:
        await query.edit_message_text("❌ مفيش مواعيد مسجلة لإلغائها.")

# معالجة اختيار الفترة (صباحًا/مساءً)
async def handle_period_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[1]
    hour = context.user_data.get('hour')
    if period == "pm":
        hour = 12 if hour == 12 else hour + 12
    elif period == "am" and hour == 12:
        hour = 0
    context.user_data['hour_24'] = hour
    await show_minute_options(query)

# عرض خيارات الدقائق
async def show_minute_options(query) -> None:
    keyboard = [
        [InlineKeyboardButton(f"{i:02d}", callback_data=f"minute_{i}") for i in range(0, 30, 5)],
        [InlineKeyboardButton(f"{i:02d}", callback_data=f"minute_{i}") for i in range(30, 60, 5)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("⏰ اختر الدقائق:", reply_markup=reply_markup)

# معالجة اختيار الدقائق
async def handle_minute_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    minute = int(query.data.split("_")[1])
    hour = context.user_data.get('hour_24')
    user_id = str(query.from_user.id)
    if hour is None:
        await query.edit_message_text("❌ يا ريت تحاول تاني باستخدام الأمر /start.")
        return

    # تخزين التوقيت الطبيعي
    users[user_id]['notifications'].append({'hour': hour, 'minute': minute})
    save_users()

    # تحويل التوقيت إلى نظام 12 ساعة
    time_12_hour = convert_to_12_hour_format(hour, minute)

    # إظهار رسالة تأكيد الموعد
    await query.edit_message_text(f"✅ تم تعيين التذكير على الساعة {time_12_hour} يوميًا.\n\n"
                                 "هتوصلك رسالة تذكير يومي في الوقت ده. ربنا يباركلك! 😊")

    # جدولة التذكير
    reminder_time = time(hour=hour, minute=minute, tzinfo=LOCAL_TIMEZONE)
    context.job_queue.run_daily(
        send_notification,
        time=reminder_time,
        days=(0, 1, 2, 3, 4, 5, 6),  # كل أيام الأسبوع
        data={'user_id': user_id}
    )
    logger.info(f"تم جدولة التذكير لـ {user_id} على الساعة {hour}:{minute}.")

# إرسال التذكير
async def send_notification(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data['user_id']
    logger.info(f"إرسال تذكير إلى المستخدم {user_id}.")
    await context.bot.send_message(
        chat_id=user_id,
        text="🎉✨ يا جماعة، متنسوش الخير! ✨🎉\n\n"
             "تذكير يومي: تبرع بجنيه واحد بس ممكن يغير حياة ناس كتير! 💸❤️\n\n"
             "لو عايز تتبرع، تقدروا تستخدموا الروابط دي:\n"
             "- 💳 [انستا باي](https://instapay.com)\n"
             "- 📱 [فودافون كاش](https://vodafonecash.com)\n\n"
             "متنسوش، الخير بيدوم والله يباركلكم! 🙏😊"
    )

# إرسال الرسالة الثابتة بعد التراويح
async def send_after_taraweeh(context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🌙✨ تذكير بعد صلاة التراويح! ✨🌙\n\n"
        "ربنا يتقبل منا ومنكم صالح الأعمال، ويجعلها في ميزان حسناتنا. 🙏\n\n"
        "متنسوش الخير، وتذكروا التبرع علشان نعيش في مجتمع أفضل. 💖"
    )

    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"فشل في إرسال الرسالة إلى المستخدم {user_id}: {e}")

# أمر سري لمعرفة عدد المستخدمين
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    # يمكنك تحديد ID الخاص بك هنا للتحقق من صلاحية الوصول
    if user_id != "1140619468":  # استبدل YOUR_ADMIN_USER_ID بمعرفك على تيليجرام
        await update.message.reply_text("❌ ليس لديك صلاحية الوصول إلى هذا الأمر.")
        return

    # حساب عدد المستخدمين الإجمالي
    total_users = len(users)

    # حساب عدد المستخدمين الذين انضموا اليوم
    today = datetime.now().strftime("%Y-%m-%d")
    today_users = sum(1 for user_data in users.values() if user_data.get('join_date') == today)

    # إرسال الإحصائيات
    stats_message = (
        f"📊 إحصائيات البوت:\n\n"
        f"👥 عدد المستخدمين الإجمالي: {total_users}\n"
        f"📅 عدد المستخدمين الذين انضموا اليوم: {today_users}"
    )
    await update.message.reply_text(stats_message)

# الدالة الرئيسية
async def main() -> None:
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("❌ مفيش توكن موجود في البيئة.")
        return
    await asyncio.sleep(60)
    application = Application.builder().token(token).build()

    # جدولة إرسال الرسائل اليومية بعد التراويح (الساعة 9 مساءً)
    job_queue = application.job_queue
    job_queue.run_daily(
        send_after_taraweeh,
        time=time(hour=21, minute=0, tzinfo=LOCAL_TIMEZONE),  # الساعة 9 مساءً
        days=(0, 1, 2, 3, 4, 5, 6)  # كل أيام الأسبوع
    )

    # إضافة handlers أخرى
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_stats))  # الأمر السري
    application.add_handler(CallbackQueryHandler(handle_hour_selection_callback, pattern="^hour_"))
    application.add_handler(CallbackQueryHandler(handle_period_selection_callback, pattern="^period_"))
    application.add_handler(CallbackQueryHandler(handle_minute_selection_callback, pattern="^minute_"))
    application.add_handler(CallbackQueryHandler(handle_hour_selection_callback, pattern="^cancel_all"))
    application.run_polling()

if __name__ == '__main__':
    main()
