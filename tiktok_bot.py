import os
import requests
import time
import re
import sys
from user_agent import generate_user_agent
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Color codes for terminal output
Z = '\033[1;31m'  # أحمر
X = '\033[1;33m'  # أصفر
F = '\033[1;32m'  # أخضر
A = '\033[1;34m'  # أزرق
C = '\033[1;35m'  # وردي
B = '\033[1;36m'  # سمائي

# TikTok API response indicator
RREP = '"status_code":0,"status_msg":"Thanks for your feedback"'

# Report types mapping
REPORT_TYPES = {
    1: ("Report content", "1"),
    2: ("Spam or harassment", "2"),
    3: ("Under 13 years of age", "3"),
    4: ("Fake information pseudonym", "4"),
    5: ("Hate speech", "5"),
    6: ("Porn", "6"),
    7: ("Terrorist organizations", "7"),
    8: ("Self-harm", "8"),
    9: ("Harassment or bullying someone I know", "9"),
}

# Telegram Bot Token
BOT_TOKEN = "7228810455:AAFcGjRFqOnNaEg1ulz0AQb90Og3AMh4WXU"

# TikTok Session ID (should be stored securely, not hardcoded)
TIKTOK_SESSION = os.getenv("TIKTOK_SESSION", "9e0696052ae90fe8842d4e619d890d1f")

# Store user data temporarily
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command - show welcome message and report type options"""
    keyboard = [
        [InlineKeyboardButton("📋 Report content", callback_data="report_1")],
        [InlineKeyboardButton("🚫 Spam or harassment", callback_data="report_2")],
        [InlineKeyboardButton("👶 Under 13 years of age", callback_data="report_3")],
        [InlineKeyboardButton("🎭 Fake information", callback_data="report_4")],
        [InlineKeyboardButton("😠 Hate speech", callback_data="report_5")],
        [InlineKeyboardButton("🔞 Porn", callback_data="report_6")],
        [InlineKeyboardButton("🚩 Terrorist organizations", callback_data="report_7")],
        [InlineKeyboardButton("⚠️ Self-harm", callback_data="report_8")],
        [InlineKeyboardButton("👥 Harassment", callback_data="report_9")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = f"""
{A}━━━━━━━━━━━━𓆩 TikTok Reporter Bot 𓆪━━━━━━━━━━━━
{F}
مرحباً! اختر نوع البلاغ:

{X}[1]{Z} Report content
{X}[2]{Z} Spam or harassment
{X}[3]{Z} Under 13 years of age
{X}[4]{Z} Fake information pseudonym
{X}[5]{Z} Hate speech
{X}[6]{Z} Porn
{X}[7]{Z} Terrorist organizations
{X}[8]{Z} Self-harm
{X}[9]{Z} Harassment or bullying
    """

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle report type selection"""
    query = update.callback_query
    await query.answer()

    # Extract report number from callback_data
    report_num = int(query.data.split("_")[1])
    user_data[query.from_user.id] = {"report_type": report_num}

    report_name = REPORT_TYPES[report_num][0]
    await query.edit_message_text(
        text=f"{F}✓ تم اختيار: {report_name}\n\nالآن أدخل اسم المستخدم المراد الإبلاغ عنه (@username):"
    )
    context.user_data["awaiting_username"] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages for username input"""
    user_id = update.message.from_user.id

    if context.user_data.get("awaiting_username"):
        target_username = update.message.text.strip()
        if target_username.startswith("@"):
            target_username = target_username[1:]

        user_data[user_id]["target"] = target_username
        context.user_data["awaiting_username"] = False

        # Get user ID from TikTok
        user_tiktok_id = await get_tiktok_user_id(target_username)

        if not user_tiktok_id:
            await update.message.reply_text(
                f"{Z}[×] خطأ: لم يتم العثور على المستخدم '{target_username}'\n"
                f"تأكد من كتابة اسم المستخدم بشكل صحيح."
            )
            return

        user_data[user_id]["tiktok_id"] = user_tiktok_id

        keyboard = [
            [InlineKeyboardButton("✓ نعم، ابدأ الإبلاغ", callback_data="start_report")],
            [InlineKeyboardButton("✗ إلغاء", callback_data="cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        report_type = user_data[user_id]["report_type"]
        report_name = REPORT_TYPES[report_type][0]

        await update.message.reply_text(
            f"{F}✓ تم العثور على المستخدم!\n\n"
            f"نوع البلاغ: {report_name}\n"
            f"المستخدم: @{target_username}\n\n"
            f"هل تريد البدء بالإبلاغ؟",
            reply_markup=reply_markup,
        )

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start sending reports"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_data:
        await query.edit_message_text(f"{Z}خطأ: لم يتم العثور على بيانات المستخدم.")
        return

    data = user_data[user_id]
    report_type = data["report_type"]
    target_username = data["target"]
    tiktok_id = data["tiktok_id"]

    await query.edit_message_text(
        f"{F}🔄 جاري الإبلاغ عن @{target_username}...\n{X}يرجى الانتظار..."
    )

    # Start reporting loop
    success_count = 0
    error_count = 0
    report_count = 0

    while report_count < 50:  # Limit to 50 reports to avoid spam
        report_count += 1
        result = await send_report(tiktok_id, report_type)

        if result:
            success_count += 1
            status = f"✓"
        else:
            error_count += 1
            status = f"✗"

        # Update message every 5 reports
        if report_count % 5 == 0:
            await query.edit_message_text(
                f"{F}📊 حالة الإبلاغات:\n"
                f"{F}✓ نجح: {success_count}\n"
                f"{Z}✗ فشل: {error_count}\n"
                f"{X}إجمالي: {report_count}/50"
            )

        time.sleep(2)  # Delay between requests

    await query.edit_message_text(
        f"{F}✓ انتهى الإبلاغ!\n\n"
        f"{F}النتائج:\n"
        f"✓ نجح: {success_count}\n"
        f"✗ فشل: {error_count}\n"
        f"إجمالي: {report_count}"
    )

    # Clean up user data
    del user_data[user_id]

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel operation"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id in user_data:
        del user_data[user_id]

    await query.edit_message_text(f"{Z}تم الإلغاء.")

async def get_tiktok_user_id(username: str) -> str:
    """Get TikTok user ID from username"""
    try:
        headers = {
            "Host": "www.tiktok.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        }

        url = f"https://www.tiktok.com/@{username}?lang=en"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Extract user ID from response
        match = re.search(r'"users":{".*":{"id":"(.*?)"', response.text)
        if match:
            return match.group(1)

        return None
    except Exception as e:
        print(f"Error getting TikTok user ID: {e}")
        return None

async def send_report(user_id: str, report_type: int) -> bool:
    """Send a single report to TikTok"""
    try:
        url = (
            f"https://www.tiktok.com/aweme/v1/aweme/feedback/"
            f"?aid=1233&app_name=tiktok_web&device_platform=web_mobile"
            f"&device_id=7008218736944907778&region=SA&priority_region=SA"
            f"&os=ios&referer=https://www.tiktok.com"
        )

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Cookie": f"sessionid={TIKTOK_SESSION}",
            "Host": "www.tiktok.com",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "User-Agent": generate_user_agent(),
        }

        data = {
            "object_id": user_id,
            "owner_id": user_id,
            "report_type": "user",
            "target": user_id,
        }

        response = requests.post(url, headers=headers, data=data, timeout=10)
        return RREP not in response.text

    except Exception as e:
        print(f"Error sending report: {e}")
        return False

def main() -> None:
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(report_callback, pattern="^report_"))
    application.add_handler(CallbackQueryHandler(start_report, pattern="^start_report$"))
    application.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    application.add_handler(CommandHandler("cancel", cancel))

    # Add message handler for username input
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    print(f"{F}🤖 البوت قيد التشغيل...")
    application.run_polling()

if __name__ == "__main__":
    main()
