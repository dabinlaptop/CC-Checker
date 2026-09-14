import logging
import os
import random
import re
from datetime import datetime
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


def generate_card_from_bin(bin_prefix, target_length=16):
  """تولید شماره کارت معتبر بر اساس یک BIN ورودی و الگوریتم Luhn"""
  bin_prefix = re.sub(r"\D", "", bin_prefix)
  card = bin_prefix

  # پر کردن ارقام میانی به صورت رندوم تا رسیدن به طول مورد نظر (منهای رقم آخر)
  while len(card) < target_length - 1:
    card += str(random.randint(0, 9))

  # پیدا کردن رقم آخر با استفاده از الگوریتم Luhn
  for d in range(10):
    test_card = card + str(d)
    if luhn_check(test_card):
      return test_card
  return card + "0"


def generate_random_exp():
  """تولید تاریخ انقضای رندوم (ماه و سال)"""
  month = f"{random.randint(1, 12):02d}"
  year = f"{random.randint(27, 32)}"  # سال‌های 2027 تا 2032
  return f"{month}/{year}"


def generate_random_cvv(card_number):
  """تولید کد CVV مناسب بر اساس نوع کارت"""
  if card_number.startswith("3"):  # آمریکن اکسپرس ۴ رقمی است
    return f"{random.randint(1000, 9999)}"
  else:
    return f"{random.randint(100, 999)}"


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

  bin_info = get_bin_info(card_number)
  return {"valid": True, "brand": brand, "bin_info": bin_info}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [
          InlineKeyboardButton(
              "⚙️ راهنمای ربات", callback_data="help_callback"
          ),
          InlineKeyboardButton(
              "🎲 کارت تستی رندوم", callback_data="generate_callback"
          ),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      "👋 **به ربات پیشرفته بررسی و تولید کارت‌های بانکی خوش آمدید!**\n\n"
      "• **بررسی تکی/گروهی:** شماره کارت‌ها را بفرستید.\n"
      "• **تولید با BIN خاص:** دستور زیر را ارسال کنید:\n"
      "  `/gen <BIN> <تعداد>`\n"
      "  *(مثال: `/gen 5154620 5`)*"
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
        "1. ارسال شماره کارت برای چک کردن اعتبار و استعلام بانک.\n"
        "2. ارسال چند شماره کارت برای چک کردن دسته‌جمعی.\n"
        "3. استفاده از `/gen 5154620` برای ساخت کارت با BIN دلخواه به همراه تاریخ و CVV.",
        parse_mode="Markdown",
    )
  elif query.data == "generate_callback":
    card = generate_card_from_bin("400300")
    exp = generate_random_exp()
    cvv = generate_random_cvv(card)
    await query.message.reply_text(
        "🎲 **کارت تستی معتبر:**\n\n"
        f"💳 `{card}`\n"
        f"📅 انقضا: `{exp}`\n"
        f"🔒 CVV: `{cvv}`",
        parse_mode="Markdown",
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """دستور جنریت کارت بر اساس BIN ورودی کاربر"""
  args = context.args
  if not args:
    await update.message.reply_text(
        "⚠️ لطفاً BIN مورد نظر را وارد کنید.\n"
        "مثال: `/gen 5154620 5`",
        parse_mode="Markdown",
    )
    return

  bin_prefix = args[0]
  count = 5  # پیش‌فرض ۵ عدد

  if len(args) > 1 and args[1].isdigit():
    count = int(args[1])
    if count > 10:
      count = 10  # حداکثر ۱۰ کارت برای جلوگیری از شلوغی

  response_text = f"⚙️ **کارت‌های تولید شده برای BIN:** `{bin_prefix}`\n\n"

  for i in range(count):
    card = generate_card_from_bin(bin_prefix)
    exp = generate_random_exp()
    cvv = generate_random_cvv(card)
    brand = get_card_brand(card)
    response_text += (
        f"**{i+1}.** `{card}` | `{exp}` | `{cvv}` | _{brand}_\n"
    )

  await update.message.reply_text(response_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  text = update.message.text
  lines = text.strip().split("\n")
  cards = []
  for line in lines:
    found = re.findall(r"\d{13,19}", line)
    cards.extend(found)

  if not cards:
    await update.message.reply_text(
        "⚠️ هیچ شماره کارت معتبری در پیام شما یافت نشد."
    )
    return

  # بررسی تک کارت
  if len(cards) == 1:
    card = cards[0]
    res = validate_single_card(card)
    exp = generate_random_exp()  # تاریخ انقضای تستی پیشنهادی
    cvv = generate_random_cvv(card)

    if res["valid"]:
      msg = (
          f"✅ **کارت معتبر است**\n`{card}`\n\n💳 **برند:**"
          f" {res['brand']}\n📅 **تاریخ پیشنهادی:** `{exp}`\n🔒 **CVV پیشنهادی:**"
          f" `{cvv}`\n"
      )
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

  # بررسی دسته‌جمعی (Bulk Check)
  valid_count = 0
  invalid_count = 0
  summary_msg = "📊 **نتیجه بررسی دسته‌جمعی:**\n\n"

  for card in cards[:20]:
    res = validate_single_card(card)
    if res["valid"]:
      valid_count += 1
      summary_msg += f"✅ `{card}` - معتبر ({res['brand']})\n"
    else:
      invalid_count += 1
      summary_msg += f"❌ `{card}` - نامعتبر\n"

  summary_msg += (
      f"\n📈 **آمار:** کل: {len(cards[:20])} | سالم: {valid_count} | خراب:"
      f" {invalid_count}"
  )
  await update.message.reply_text(summary_msg, parse_mode="Markdown")


def main():
  token = os.getenv("BOT_TOKEN")
  if not token:
    print("خطا: توکن ربات (BOT_TOKEN) تنظیم نشده است.")
    return

  app = ApplicationBuilder().token(token).build()

  app.add_handler(CommandHandler("start", start_command))
  app.add_handler(CommandHandler("gen", generate_command))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  print("ربات پیشرفته همراه با قابلیت تولید کارت آماده به کار است...")
  app.run_polling()


if __name__ == "__main__":
  main()
