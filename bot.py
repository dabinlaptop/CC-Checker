import logging
import os
import random
import re
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def luhn_check(card_number):
  """الگوریتم Luhn برای بررسی اعتبار ریاضی کارت"""
  digits = [int(c) for c in card_number]
  checksum = 0
  for i, digit in enumerate(reversed(digits)):
    if i % 2 == 1:
      doubled = digit * 2
      if doubled > 9:
        doubled -= 9
      checksum += doubled
    else:
      checksum += digit
  return checksum % 10 == 0


def get_card_brand(card_number):
  """تشخیص برند کارت بین‌المللی"""
  if re.match(r"^4[0-9]{12}(?:[0-9]{3})?(?:[0-9]{3})?$", card_number):
    return "Visa 💳"
  elif re.match(
      r"^(5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}$",
      card_number,
  ):
    return "Mastercard 💳"
  elif re.match(r"^3[47][0-9]{13}$", card_number):
    return "American Express (Amex) 💳"
  elif re.match(r"^(6011|65[0-9]{2}|64[4-9][0-9])[0-9]{12,15}$", card_number):
    return "Discover 💳"
  else:
    return "سایر / نامشخص ❓"


def get_bin_info(card_number):
  """استعلام اطلاعات BIN از سرویس آنلاین بین‌المللی"""
  bin_code = card_number[:6]
  try:
    response = requests.get(
        f"https://lookup.binlist.net/{bin_code}",
        headers={"Accept-Version": "3"},
        timeout=3,
    )
    if response.status_code == 200:
      data = response.json()
      return {
          "scheme": data.get("scheme", "نامشخص").upper(),
          "type": data.get("type", "نامشخص").upper(),
          "brand": data.get("brand", "نامشخص"),
          "country": data.get("country", {}).get("name", "نامشخص"),
          "bank": data.get("bank", {}).get("name", "نامشخص"),
      }
  except Exception:
    pass
  return None


def generate_valid_card(prefix="4"):
  """تولید شماره کارت تستی معتبر بر اساس الگوریتم Luhn"""
  card = prefix
  length = 16
  while len(card) < length - 1:
    card += str(random.randint(0, 9))

  for d in range(10):
    test_card = card + str(d)
    if luhn_check(test_card):
      return test_card
  return card + "0"


def validate_single_card(card_number):
  card_number = re.sub(r"\D", "", card_number)
  if len(card_number) < 13 or len(card_number) > 19:
    return {"valid": False, "message": "طول کارت نامعتبر (۱۳ تا ۱۹ رقم)."}

  brand = get_card_brand(card_number)
  if not luhn_check(card_number):
    return {
        "valid": False,
        "brand": brand,
        "message": "رد شده در الگوریتم Luhn (ساختار ریاضی نادرست).",
    }

  # دریافت اطلاعات تکمیلی BIN
  bin_info = get_bin_info(card_number)

  return {"valid": True, "brand": brand, "bin_info": bin_info}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [
          InlineKeyboardButton(
              "⚙️ راهنمای ربات", callback_data="help_callback"
          ),
          InlineKeyboardButton(
              "🎲 تولید کارت تستی", callback_data="generate_callback"
          ),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      "👋 **به ربات پیشرفته بررسی کارت‌های بین‌المللی خوش آمدید!**\n\n"
      "• برای بررسی **تک کارت**، شماره آن را بفرستید.\n"
      "• برای بررسی **دسته‌جمعی**، چند شماره کارت را در خطوط مختلف بفرستید.\n"
      "• برای تولید کارت تستی از دستور `/generate` استفاده کنید."
  )
  await update.message.reply_text(
      welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  if query.data == "help_callback":
    await query.message.reply_text(
        "📖 **راهنمای استفاده:**\n\n"
        "این ربات کارت‌های Visa، Mastercard و... را از نظر ساختار ریاضی و اطلاعات بانک صادرکننده چک می‌کند.\n"
        "می‌توانید به صورت گروهی یا تکی کارت بفرستید.",
        parse_mode="Markdown",
    )
  elif query.data == "generate_callback":
    visa_card = generate_valid_card("4")
    master_card = generate_valid_card("51")
    await query.message.reply_text(
        "🎲 **کارت‌های تستی معتبر:**\n\n"
        f"💳 **Visa:** `{visa_card}`\n"
        f"💳 **Mastercard:** `{master_card}`",
        parse_mode="Markdown",
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  visa_card = generate_valid_card("4")
  master_card = generate_valid_card("51")
  await update.message.reply_text(
      "🎲 **کارت‌های تستی معتبر جدید:**\n\n"
      f"💳 **Visa:** `{visa_card}`\n"
      f"💳 **Mastercard:** `{master_card}`",
      parse_mode="Markdown",
  )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  text = update.message.text
  # استخراج تمام خطوط یا کلمات به عنوان کارت‌های احتمالی
  lines = text.strip().split("\n")
  cards = []
  for line in lines:
    # پیدا کردن اعداد درون متن
    found = re.findall(r"\d{13,19}", line)
    cards.extend(found)

  if not cards:
    await update.message.reply_text(
        "⚠️ هیچ شماره کارت معتبری در پیام شما یافت نشد."
    )
    return

  # اگر فقط یک کارت بود، جزئیات کامل نمایش بده
  if len(cards) == 1:
    card = cards[0]
    res = validate_single_card(card)
    if res["valid"]:
      msg = f"✅ **کارت معتبر است**\n`{card}`\n\n💳 **برند:** {res['brand']}\n"
      if res["bin_info"]:
        bi = res["bin_info"]
        msg += (
            f"🌍 **کشور:** {bi['country']}\n🏦 **بانک:** {bi['bank']}\n📋"
            f" **نوع:** {bi['type']} ({bi['scheme']})"
        )
    else:
      msg = (
          f"❌ **کارت نامعتبر است**\n`{card}`\n⚠️ **دلیل:** {res['message']}"
      )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return

  # اگر چند کارت بود (Bulk Check)
  valid_count = 0
  invalid_count = 0
  summary_msg = "📊 **نتیجه بررسی دسته‌جمعی:**\n\n"

  for card in cards[:20]:  # محدود کردن به حداکثر ۲۰ کارت در هر پیام
    res = validate_single_card(card)
    if res["valid"]:
      valid_count += 1
      summary_msg += f"✅ `{card}` - معتبر ({res['brand']})\n"
    else:
      invalid_count += 1
      summary_msg += f"❌ `{card}` - نامعتبر\n"

  summary_msg += (
      f"\n📈 **آمار کلی:**\nکل بررسی‌شده: {len(cards[:20])} | سالم: {valid_count}"
      f" | خراب: {invalid_count}"
  )
  await update.message.reply_text(summary_msg, parse_mode="Markdown")


def main():
  token = os.getenv("BOT_TOKEN")
  if not token:
    print("خطا: توکن ربات (BOT_TOKEN) تنظیم نشده است.")
    return

  app = ApplicationBuilder().token(token).build()

  app.add_handler(CommandHandler("start", start_command))
  app.add_handler(CommandHandler("generate", generate_command))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  print("ربات پیشرفته با موفقیت روشن شد و آماده به کار است...")
  app.run_polling()


if __name__ == "__main__":
  main()
