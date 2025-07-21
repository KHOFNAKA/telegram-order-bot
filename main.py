import os
import re
import json
from flask import Flask, request
import requests
import uuid
from datetime import datetime

app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ORDER_FILE = "orders.txt"
sessions = {}

# دیتابیس سفارشات در حافظه برای انتخاب سریع ادمین
orders_db = {}

def save_order(data):
    with open(ORDER_FILE, "a", encoding="utf-8") as f:
        f.write(data + "\n" + "="*50 + "\n")

def read_orders():
    try:
        with open(ORDER_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "هیچ سفارشی ثبت نشده است."

def validate_phone(phone):
    """اعتبارسنجی شماره تلفن ایرانی"""
    phone = phone.strip().replace(" ", "").replace("-", "")
    pattern = r'^(\+98|0098|98|0)?9\d{9}$'
    return bool(re.match(pattern, phone))

def validate_email(email):
    """اعتبارسنجی ایمیل"""
    if email.strip() == "." or email.strip() == "":
        return True  # ایمیل اختیاری است
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def create_glass_keyboard(buttons_data):
    """ساخت کیبورد شیشه‌ای جذاب"""
    keyboard = {
        "inline_keyboard": []
    }
    
    for row in buttons_data:
        button_row = []
        for button in row:
            button_row.append({
                "text": f"✨ {button['text']} ✨",
                "callback_data": button['callback']
            })
        keyboard["inline_keyboard"].append(button_row)
    
    return keyboard

def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        payload["reply_markup"] = keyboard
    
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json=payload
    )

def edit_message(chat_id, message_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if keyboard:
        payload["reply_markup"] = keyboard
    
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/editMessageText",
        json=payload
    )

def answer_callback_query(callback_query_id, text=""):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id, "text": text}
    )

def get_business_keyboard():
    return create_glass_keyboard([
        [{"text": "شخصی", "callback": "business_personal"}, {"text": "شرکتی", "callback": "business_company"}],
        [{"text": "خدماتی", "callback": "business_service"}, {"text": "فروشگاهی", "callback": "business_shop"}],
        [{"text": "وبلاگ", "callback": "business_blog"}, {"text": "آموزشی", "callback": "business_education"}],
        [{"text": "سایر موارد", "callback": "business_other"}]
    ])

def get_purpose_keyboard():
    return create_glass_keyboard([
        [{"text": "معرفی خدمات", "callback": "purpose_services"}, {"text": "جذب مشتری", "callback": "purpose_customers"}],
        [{"text": "فروش آنلاین", "callback": "purpose_sales"}, {"text": "ارائه محتوا", "callback": "purpose_content"}],
        [{"text": "نمونه کار", "callback": "purpose_portfolio"}, {"text": "رزومه", "callback": "purpose_resume"}],
        [{"text": "سایر موارد", "callback": "purpose_other"}]
    ])

def get_yes_no_keyboard(action):
    return create_glass_keyboard([
        [{"text": "✅ بله", "callback": f"{action}_yes"}, {"text": "❌ خیر", "callback": f"{action}_no"}]
    ])

def get_cancel_keyboard():
    """کیبورد لغو سفارش"""
    return create_glass_keyboard([
        [{"text": "🚫 لغو سفارش", "callback": "cancel_order"}]
    ])

def get_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "🏠 شروع مجدد"}, {"text": "🚫 لغو سفارش"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_admin_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "📋 مشاهده سفارشات"}],
            [{"text": "💰 اعلام قیمت"}, {"text": "❌ رد سفارش"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_orders_selection_keyboard():
    keyboard_data = []
    active_orders = []
    
    for sess_key, sess in sessions.items():
        if sess.get("order_id") and sess.get("step") == "completed":
            order_id = sess["order_id"]
            customer_name = sess.get("name", "نامشخص")
            active_orders.append({
                "text": f"{order_id} - {customer_name}",
                "callback": f"select_order_{order_id}"
            })
    
    # ایجاد ردیف‌های دکمه (2 دکمه در هر ردیف)
    for i in range(0, len(active_orders), 2):
        row = active_orders[i:i+2]
        keyboard_data.append(row)
    
    if not keyboard_data:
        keyboard_data.append([{"text": "❌ سفارش فعالی وجود ندارد", "callback": "no_orders"}])
    
    return create_glass_keyboard(keyboard_data)

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    
    if "callback_query" in data:
        return handle_callback_query(data["callback_query"])
    
    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = str(message["chat"]["id"])
    text = message.get("text", "")

    # مدیریت ادمین
    if chat_id == ADMIN_CHAT_ID:
        return handle_admin_message(chat_id, text)

    # مدیریت پیام‌های کاربران عادی
    return handle_user_message(chat_id, text, message)

def handle_callback_query(callback_query):
    chat_id = str(callback_query["from"]["id"])
    callback_data = callback_query["data"]
    message_id = callback_query["message"]["message_id"]
    callback_query_id = callback_query["id"]

    # پاسخ به callback query
    answer_callback_query(callback_query_id)

    if chat_id == ADMIN_CHAT_ID:
        return handle_admin_callback(chat_id, callback_data, message_id)
    else:
        return handle_user_callback(chat_id, callback_data, message_id)

def handle_admin_callback(chat_id, callback_data, message_id):
    if callback_data.startswith("select_order_"):
        order_id = callback_data.replace("select_order_", "")
        admin_session = sessions.get(chat_id, {})
        action = admin_session.get("admin_action")
        
        if action == "price":
            edit_message(chat_id, message_id, f"<b>💰 قیمت برای سفارش {order_id}:</b>\nلطفاً مبلغ را به تومان وارد کنید:")
            sessions[chat_id] = {"admin_action": "price", "selected_order": order_id, "step": "waiting_price"}
        elif action == "reject":
            edit_message(chat_id, message_id, f"<b>❌ رد سفارش {order_id}:</b>\nلطفاً دلیل رد را وارد کنید:")
            sessions[chat_id] = {"admin_action": "reject", "selected_order": order_id, "step": "waiting_reason"}
    elif callback_data == "no_orders":
        edit_message(chat_id, message_id, "❌ <b>هیچ سفارش فعالی وجود ندارد!</b>", get_admin_menu_keyboard())

    return {"ok": True}

def handle_user_callback(chat_id, callback_data, message_id):
    sess = sessions.get(chat_id, {})
    
    if callback_data == "cancel_order":
        edit_message(chat_id, message_id, "❌ <b>سفارش لغو شد.</b>\nبرای شروع مجدد /start را ارسال کنید.")
        sessions.pop(chat_id, None)
        return {"ok": True}

    # مدیریت انتخاب نوع کسب‌وکار
    if callback_data.startswith("business_"):
        business_type = callback_data.replace("business_", "")
        if business_type == "other":
            edit_message(chat_id, message_id, "💼 <b>نوع کسب‌وکار خود را به صورت متن وارد کنید:</b>", get_cancel_keyboard())
            sess["step"] = "business_custom"
        else:
            business_map = {
                "personal": "شخصی", "company": "شرکتی", "service": "خدماتی",
                "shop": "فروشگاهی", "blog": "وبلاگ", "education": "آموزشی"
            }
            sess["business"] = business_map.get(business_type, business_type)
            sess["step"] = "purpose"
            edit_message(chat_id, message_id, "🎯 <b>هدف از ایجاد وب‌سایت خود را انتخاب کنید:</b>", get_purpose_keyboard())
        sessions[chat_id] = sess

    # مدیریت انتخاب هدف وب‌سایت
    elif callback_data.startswith("purpose_"):
        purpose_type = callback_data.replace("purpose_", "")
        if purpose_type == "other":
            edit_message(chat_id, message_id, "🎯 <b>هدف از وب‌سایت خود را به صورت متن وارد کنید:</b>", get_cancel_keyboard())
            sess["step"] = "purpose_custom"
        else:
            purpose_map = {
                "services": "معرفی خدمات", "customers": "جذب مشتری", "sales": "فروش آنلاین",
                "content": "ارائه محتوا", "portfolio": "نمونه کار", "resume": "رزومه"
            }
            sess["purpose"] = purpose_map.get(purpose_type, purpose_type)
            sess["step"] = "features"
            edit_message(chat_id, message_id, "⚡ <b>ویژگی‌های مدنظر خود را بنویسید:</b>\n<i>(مثال: گالری تصاویر، فرم تماس، وبلاگ، درگاه پرداخت)</i>", get_cancel_keyboard())
        sessions[chat_id] = sess

    # مدیریت انتخاب دامنه و هاست
    elif callback_data.startswith("domain_"):
        answer = "بله" if callback_data == "domain_yes" else "خیر"
        sess["domain"] = answer
        sess["step"] = "extra"
        edit_message(chat_id, message_id, "📝 <b>توضیحات تکمیلی (اختیاری):</b>\n<i>هر چیزی که فکر می‌کنید باید بدانیم یا نقطه برای رد کردن</i>", get_cancel_keyboard())
        sessions[chat_id] = sess

    # مدیریت انتخاب پشتیبانی
    elif callback_data.startswith("support_"):
        answer = "بله" if callback_data == "support_yes" else "خیر"
        sess["support"] = answer
        
        # ایجاد شناسه سفارش
        order_id = "ORD-" + uuid.uuid4().hex[:8].upper()
        sess["order_id"] = order_id
        
        # خلاصه سفارش
        summary = f"""
🔖 <b>شناسه سفارش:</b> <code>{order_id}</code>
👤 <b>نام:</b> {sess.get('name', '')}
📱 <b>شماره:</b> {sess.get('phone', '')}
📧 <b>ایمیل:</b> {sess.get('email', 'وارد نشده')}
💼 <b>نوع کسب‌وکار:</b> {sess.get('business', '')}
🎯 <b>هدف:</b> {sess.get('purpose', '')}
⚡ <b>ویژگی‌ها:</b> {sess.get('features', '')}
🌐 <b>دامنه/هاست:</b> {sess.get('domain', '')}
📝 <b>توضیحات:</b> {sess.get('extra', 'ندارد')}
🛠 <b>پشتیبانی:</b> {answer}
        """
        
        confirm_keyboard = create_glass_keyboard([
            [{"text": "✅ تأیید و ارسال", "callback": "confirm_yes"}],
            [{"text": "❌ لغو سفارش", "callback": "confirm_no"}]
        ])
        
        edit_message(chat_id, message_id, f"<b>📋 لطفاً اطلاعات را بررسی کنید:</b>{summary}", confirm_keyboard)
        sess["step"] = "confirm"
        sessions[chat_id] = sess

    # مدیریت تأیید نهایی
    elif callback_data == "confirm_yes":
        # ذخیره سفارش
        order_text = f"""
OrderID: {sess.get('order_id', '')}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Name: {sess.get('name', '')}
Phone: {sess.get('phone', '')}
Email: {sess.get('email', '')}
Business Type: {sess.get('business', '')}
Website Purpose: {sess.get('purpose', '')}
Features: {sess.get('features', '')}
Has Domain/Host: {sess.get('domain', '')}
Extra Info: {sess.get('extra', '')}
Support: {sess.get('support', '')}
Chat ID: {chat_id}
        """
        
        save_order(order_text)
        
        # اعلام به ادمین
        admin_text = f"🆕 <b>سفارش جدید دریافت شد!</b>\n\n<pre>{order_text}</pre>"
        send_message(ADMIN_CHAT_ID, admin_text)
        
        # پیام تأیید به مشتری
        edit_message(chat_id, message_id, "✅ <b>سفارش شما با موفقیت ثبت شد!</b>\n\n🔖 شناسه سفارش: <code>" + sess.get('order_id', '') + "</code>\n\n⏳ کارشناسان ما در حال بررسی درخواست شما هستند و به زودی قیمت اعلام خواهد شد.\n\n📞 در صورت نیاز با پشتیبانی تماس بگیرید.")
        
        sess["step"] = "completed"
        sessions[chat_id] = sess

    elif callback_data == "confirm_no":
        edit_message(chat_id, message_id, "❌ <b>سفارش لغو شد.</b>\nبرای شروع مجدد /start را ارسال کنید.")
        sessions.pop(chat_id, None)

    return {"ok": True}

def handle_admin_message(chat_id, text):
    admin_sess = sessions.get(chat_id, {})
    
    if text == "/start" or text == "🏠 شروع مجدد":
        send_message(chat_id, "👨‍💼 <b>خوش آمدید ادمین عزیز!</b>\n\n🎛 <b>پنل مدیریت:</b>", get_admin_menu_keyboard())
        return {"ok": True}
    
    # مدیریت دستورات منوی کیبورد
    if text == "📋 مشاهده سفارشات":
        orders = read_orders()
        send_message(chat_id, f"<b>📋 لیست سفارشات:</b>\n\n<pre>{orders}</pre>", get_admin_menu_keyboard())
        return {"ok": True}
    
    elif text == "💰 اعلام قیمت":
        send_message(chat_id, "<b>💰 انتخاب سفارش برای اعلام قیمت:</b>", get_orders_selection_keyboard())
        sessions[chat_id] = {"admin_action": "price"}
        return {"ok": True}
    
    elif text == "❌ رد سفارش":
        send_message(chat_id, "<b>❌ انتخاب سفارش برای رد:</b>", get_orders_selection_keyboard())
        sessions[chat_id] = {"admin_action": "reject"}
        return {"ok": True}
    
    # مدیریت ورودی قیمت
    if admin_sess.get("step") == "waiting_price":
        try:
            price = int(text.replace(",", "").replace("تومان", "").strip())
            order_id = admin_sess["selected_order"]
            
            # پیدا کردن مشتری
            target_chat_id = None
            target_name = None
            for sess_key, sess in sessions.items():
                if sess.get("order_id") == order_id:
                    target_chat_id = sess_key  # چت آیدی در کلید سشن ذخیره شده
                    target_name = sess.get("name")
                    break
            
            if target_chat_id:
                customer_message = f"💰 <b>سلام {target_name} عزیز!</b>\n\n✨ قیمت پروژه شما <b>{price:,} تومان</b> برآورد شده است.\n\n📞 برای هماهنگی بیشتر و شروع پروژه لطفاً با شماره پشتیبانی تماس بگیرید.\n\n🔖 شناسه سفارش: <code>{order_id}</code>"
                send_message(target_chat_id, customer_message)
                send_message(chat_id, f"✅ <b>قیمت با موفقیت اعلام شد!</b>\n\n💰 مبلغ: <b>{price:,} تومان</b>\n🔖 سفارش: <code>{order_id}</code>", get_admin_menu_keyboard())
            else:
                send_message(chat_id, "❌ <b>خطا:</b> سفارش یافت نشد!", get_admin_menu_keyboard())
            
            sessions.pop(chat_id, None)
        except ValueError:
            send_message(chat_id, "❌ <b>خطا:</b> لطفاً مبلغ را به عدد وارد کنید!")

    # مدیریت ورودی دلیل رد
    elif admin_sess.get("step") == "waiting_reason":
        reason = text.strip()
        order_id = admin_sess["selected_order"]
        
        # پیدا کردن مشتری
        target_chat_id = None
        target_name = None
        for sess_key, sess in sessions.items():
            if sess.get("order_id") == order_id:
                target_chat_id = sess_key  # چت آیدی در کلید سشن ذخیره شده
                target_name = sess.get("name")
                break
        
        if target_chat_id:
            customer_message = f"❌ <b>مشتری عزیز {target_name}</b>\n\nمتأسفانه درخواست شما بررسی شد و به دلیل <b>{reason}</b> امکان همکاری فراهم نیست.\n\n🙏 از صبوری و درک شما سپاسگزاریم.\n\n🔖 شناسه سفارش: <code>{order_id}</code>"
            send_message(target_chat_id, customer_message)
            send_message(chat_id, f"✅ <b>سفارش با موفقیت رد شد!</b>\n\n🔖 سفارش: <code>{order_id}</code>\n📝 دلیل: {reason}", get_admin_menu_keyboard())
            
            # حذف سشن مشتری
            sessions_to_remove = [k for k, v in sessions.items() if v.get("order_id") == order_id]
            for k in sessions_to_remove:
                sessions.pop(k, None)
        else:
            send_message(chat_id, "❌ <b>خطا:</b> سفارش یافت نشد!", get_admin_menu_keyboard())
        
        sessions.pop(chat_id, None)

    return {"ok": True}

def handle_user_message(chat_id, text, message):
    if text == "/start" or text == "🏠 شروع مجدد":
        sessions[chat_id] = {"step": "name", "chat_id": chat_id}
        welcome_msg = """
🌟 <b>سلام! به سیستم سفارش وب‌سایت خوش آمدید</b> 🌟

✨ ما آماده ایجاد بهترین وب‌سایت برای شما هستیم!

👤 <b>لطفاً نام و نام خانوادگی خود را وارد کنید:</b>
        """
        send_message(chat_id, welcome_msg, get_menu_keyboard())
        return {"ok": True}
    
    # مدیریت لغو سفارش
    if text == "🚫 لغو سفارش":
        send_message(chat_id, "❌ <b>سفارش لغو شد.</b>\nبرای شروع مجدد 'شروع مجدد' را انتخاب کنید.", get_menu_keyboard())
        sessions.pop(chat_id, None)
        return {"ok": True}

    sess = sessions.get(chat_id)
    if not sess:
        send_message(chat_id, "🔄 <b>لطفاً ابتدا 'شروع مجدد' را انتخاب کنید.</b>", get_menu_keyboard())
        return {"ok": True}

    step = sess["step"]
    
    if step == "name":
        if len(text.strip()) < 2:
            send_message(chat_id, "❌ <b>نام وارد شده کوتاه است!</b>\nلطفاً نام کامل خود را وارد کنید:", get_menu_keyboard())
            return {"ok": True}
        sess["name"] = text.strip()
        sess["step"] = "phone"
        send_message(chat_id, "📱 <b>شماره تماس خود را وارد کنید:</b>\n<i>(مثال: 09123456789)</i>", get_menu_keyboard())

    elif step == "phone":
        if not validate_phone(text):
            send_message(chat_id, "❌ <b>شماره تلفن نامعتبر است!</b>\nلطفاً شماره معتبر وارد کنید:\n<i>(مثال: 09123456789)</i>", get_menu_keyboard())
            return {"ok": True}
        sess["phone"] = text.strip()
        sess["step"] = "email"
        send_message(chat_id, "📧 <b>ایمیل خود را وارد کنید:</b>\n<i>(اختیاری - برای رد کردن نقطه بگذارید: .)</i>", get_menu_keyboard())

    elif step == "email":
        if not validate_email(text):
            send_message(chat_id, "❌ <b>ایمیل نامعتبر است!</b>\nلطفاً ایمیل معتبر وارد کنید یا برای رد کردن نقطه بگذارید:", get_menu_keyboard())
            return {"ok": True}
        sess["email"] = text.strip() if text.strip() != "." else ""
        sess["step"] = "business"
        send_message(chat_id, "💼 <b>نوع کسب‌وکار خود را انتخاب کنید:</b>", get_business_keyboard())

    elif step == "business_custom":
        sess["business"] = text.strip()
        sess["step"] = "purpose"
        send_message(chat_id, "🎯 <b>هدف از ایجاد وب‌سایت خود را انتخاب کنید:</b>", get_purpose_keyboard())

    elif step == "purpose_custom":
        sess["purpose"] = text.strip()
        sess["step"] = "features"
        send_message(chat_id, "⚡ <b>ویژگی‌های مدنظر خود را بنویسید:</b>\n<i>(مثال: گالری تصاویر، فرم تماس، وبلاگ، درگاه پرداخت)</i>", get_menu_keyboard())

    elif step == "features":
        sess["features"] = text.strip()
        sess["step"] = "domain"
        send_message(chat_id, "🌐 <b>آیا دامنه و هاست دارید؟</b>", get_yes_no_keyboard("domain"))

    elif step == "extra":
        sess["extra"] = text.strip()
        sess["step"] = "support"
        send_message(chat_id, "🛠 <b>آیا مایل به دریافت خدمات پشتیبانی هستید؟</b>", get_yes_no_keyboard("support"))

    sessions[chat_id] = sess
    return {"ok": True}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
