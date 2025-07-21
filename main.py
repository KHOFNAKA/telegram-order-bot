import os
from flask import Flask, request
import requests
import uuid

app = Flask(name)
TOKEN = os.getenv("BOT_TOKEN")  # توکن ربات رو به صورت متغیر محیطی تنظیم می‌کنیم
ADMIN = os.getenv("ADMIN_USERNAME", "KHOFNAKA")  # یوزرنیم ادمین

ORDER_FILE = "orders.txt"
sessions = {}

def save_order(data):
    with open(ORDER_FILE, "a", encoding="utf-8") as f:
        f.write(data + "\n----\n")

def send_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def process_admin_command(cmd_text):
    parts = cmd_text.split(maxsplit=2)
    action = parts[0]
    if action not in ["/price", "/reject"]:
        return False

    if len(parts) < 2:
        return False

    order_id = parts[1]
    reason_or_price = parts[2] if len(parts) > 2 else ""

    # جستجو در sessions برای پیدا کردن چت آیدی و نام مشتری
    target_chat_id = None
    target_name = None
    for sess in sessions.values():
        if sess.get("order_id") == order_id:
            target_chat_id = sess.get("chat_id")
            target_name = sess.get("name")
            break

    if not target_chat_id:
        return False

    if action == "/price":
        msg = f"سلام {target_name} عزیز، قیمت پروژه شما {reason_or_price} تومان است. برای هماهنگی بیشتر لطفاً با شماره تماس بگیرید."
        send_message(target_chat_id, msg)
        return True

    if action == "/reject":
        msg = f"مشتری عزیز {target_name}، درخواست شما بررسی شد."
        if reason_or_price:
            msg += f" به دلیل {reason_or_price} امکان همکاری نیست."
        msg += " از صبوری و درک شما سپاسگزاریم."
        send_message(target_chat_id, msg)
        return True

    return False

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    # اگر پیام از ادمین بود و دستور price یا reject داد
    if "username" in message["from"]:
        sender_username = message["from"]["username"]
    else:
        sender_username = ""

    if sender_username == ADMIN and (text.startswith("/price") or text.startswith("/reject")):
        handled = process_admin_command(text)
        if handled:
            send_message(chat_id, "✅ دستور انجام شد.")
            return {"ok": True}

    # شروع مکالمه کاربر
    if text == "/start":
        sessions[str(chat_id)] = {"step": "name", "chat_id": chat_id}
        send_message(chat_id, "سلام! لطفاً نام و نام خانوادگی خود را وارد کنید:")
        return {"ok": True}

    sess = sessions.get(str(chat_id))
    if not sess:
        send_message(chat_id, "لطفاً ابتدا /start را بزنید.")
        return {"ok": True}

    step = sess["step"]

    if step == "name":
        sess["name"] = text
        sess["step"] = "phone"
        send_message(chat_id, "شماره تماس خود را وارد کنید:")
    elif step == "phone":
        sess["phone"] = text
        sess["step"] = "email"
        send_message(chat_id, "ایمیل خود را وارد کنید (اختیاری):")
    elif step == "email":
        sess["email"] = text
        sess["step"] = "business"
        send_message(chat_id, "نوع کسب‌وکار خود را وارد کنید (مثلاً شخصی، شرکتی، خدماتی، وبلاگ):")
    elif step == "business":
        sess["business"] = text
        sess["step"] = "purpose"
        send_message(chat_id, "هدف از وب‌سایت خود را وارد کنید (مثلاً معرفی خدمات، جذب مشتری، ارائه محتوا):")
    elif step == "purpose":
        sess["purpose"] = text
        sess["step"] = "features"
        send_message(chat_id, "ویژگی‌های مدنظر خود را بنویسید (مثلاً گالری تصاویر، فرم تماس، وبلاگ):")

sina, [21.07.2025 16:18]
elif step == "features":
        sess["features"] = text
        sess["step"] = "domain"
        send_message(chat_id, "آیا دامنه و هاست دارید؟ (بله/خیر):")
    elif step == "domain":
        sess["domain"] = text
        sess["step"] = "extra"
        send_message(chat_id, "توضیحات تکمیلی (در صورت وجود):")
    elif step == "extra":
        sess["extra"] = text
        sess["step"] = "support"
        send_message(chat_id, "آیا مایل به دریافت خدمات پشتیبانی هستید؟ (بله/خیر):")
    elif step == "support":
        sess["support"] = text
        # ایجاد شناسه سفارش منحصر بفرد
        order_id = "ORD-" + uuid.uuid4().hex[:8].upper()
        sess["order_id"] = order_id

        summary = (
            f"شناسه سفارش: {order_id}\n"
            f"نام و نام خانوادگی: {sess.get('name','')}\n"
            f"شماره تماس: {sess.get('phone','')}\n"
            f"ایمیل: {sess.get('email','')}\n"
            f"نوع کسب‌وکار: {sess.get('business','')}\n"
            f"هدف وب‌سایت: {sess.get('purpose','')}\n"
            f"ویژگی‌ها: {sess.get('features','')}\n"
            f"دامنه/هاست: {sess.get('domain','')}\n"
            f"توضیحات تکمیلی: {sess.get('extra','')}\n"
            f"پشتیبانی: {sess.get('support','')}\n"
        )
        send_message(chat_id, "لطفاً اطلاعات زیر را بررسی و تأیید کنید:\n\n" + summary + "\nبرای تأیید 'بله' و برای لغو 'خیر' را ارسال کنید.")
        sess["step"] = "confirm"
    elif step == "confirm":
        if text.strip().lower() in ["بله", "بلی", "yes"]:
            # ذخیره سفارش در فایل
            order_text = (
                f"OrderID: {sess.get('order_id','')}\n"
                f"Name: {sess.get('name','')}\n"
                f"Phone: {sess.get('phone','')}\n"
                f"Email: {sess.get('email','')}\n"
                f"Business Type: {sess.get('business','')}\n"
                f"Website Purpose: {sess.get('purpose','')}\n"
                f"Features: {sess.get('features','')}\n"
                f"Has Domain/Host: {sess.get('domain','')}\n"
                f"Extra Info: {sess.get('extra','')}\n"
                f"Support: {sess.get('support','')}\n"
                f"Telegram Username: @{message['from'].get('username','')}\n"
            )
            save_order(order_text)

            # ارسال سفارش به ادمین
            send_message(f"@{ADMIN}", f"سفارش جدید:\n{order_text}")

            send_message(chat_id, "✅ اطلاعات شما ثبت شد. کارشناسان ما در حال بررسی هستند و به زودی قیمت اعلام می‌شود.")
            sessions.pop(str(chat_id), None)
        else:
            send_message(chat_id, "❌ سفارش لغو شد. برای شروع مجدد /start را بزنید.")
            sessions.pop(str(chat_id), None)
    else:
        send_message(chat_id, "لطفاً از دستور /start برای شروع استفاده کنید.")

    return {"ok": True}


if name == "main":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
