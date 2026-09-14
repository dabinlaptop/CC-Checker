import logging
import os
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
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
  """الگوریتم Luhn برای بررسی اعتبار کارت‌های بانکی"""
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


def validate_foreign_card(card_number):
  card_number = re.sub(r"\D", "", card_number)

  if len(card_number) < 13 or len(card_number) > 19:
    return {
        "valid": False,
        "brand": "نامشخص",
        "message": "طول شماره کارت نامعتبر است (باید بین ۱۳ تا ۱۹ رقم باشد).",
    }

  brand = get_card_brand(card_number)

  if not luhn_check(card_number):
    return {
        "valid": False,
        "brand": brand,
        "message": "شماره کارت از نظر ساختار ریاضی (الگوریتم Luhn) نامعتبر است.",
    }

  return {
      "valid": True,
      "brand": brand,
      "message": "شماره کارت از نظر ساختار کاملاً معتبر است.",
  }


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_text = update.message.text
  result = validate_foreign_card(user_text)

  if result["valid"]:
    response = (
        f"✅ **نتیجه بررسی: معتبر**\n\n"
        f"💳 **برند کارت:** {result['brand']}\n"
        f"📝 **توضیحات:** {result['message']}"
    )
  else:
    response = (
        f"❌ **نتیجه بررسی: نامعتبر**\n\n"
        f"💳 **برند کارت:** {result['brand']}\n"
        f"⚠️ **دلیل:** {result['message']}"
    )

  await update.message.reply_text(response, parse_mode="Markdown")


def main():
  token = os.getenv("BOT_TOKEN")
  if not token:
    print("خطا: توکن ربات (BOT_TOKEN) تنظیم نشده است.")
    return

  app = ApplicationBuilder().token(token).build()
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  print("ربات با موفقیت روشن شد و در حال گوش دادن به پیام‌هاست...")
  app.run_polling()


if __name__ == "__main__":
  main()
