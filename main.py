import os
import re
import json
from flask import Flask, request
import requests
import uuid
from datetime import datetime
from jdatetime import datetime as jdatetime

app = Flask(__name__)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ORDER_FILE = "orders.txt"
ORDERS_JSON = "orders.json"
sessions = {}
orders_db = {}

def save_order(data, order_data=None):
    # Save to text file
    with open(ORDER_FILE, "a", encoding="utf-8") as f:
        f.write(data + "\n" + "="*50 + "\n")
    
    # Save to JSON for better management
    if order_data:
        try:
            with open(ORDERS_JSON, "r", encoding="utf-8") as f:
                orders = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            orders = []
        
        orders.append(order_data)
        with open(ORDERS_JSON, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)

def read_orders():
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            orders = json.load(f)
        
        if not orders:
            return "هیچ سفارشی ثبت نشده است."
        
        formatted_orders = "📋 **لیست سفارشات:**\n\n"
        for order in orders[-10:]:  # Show last 10 orders
            status_emoji = {
                "pending": "⏳",
                "priced": "💰", 
                "completed": "✅",
                "rejected": "❌"
            }
            emoji = status_emoji.get(order.get("status", "pending"), "⏳")
            
            formatted_orders += f"""
{emoji} **سفارش {order['order_id']}**
👤 {order['name']} | 📱 {order['phone']}
💼 {order['business']} | 🎯 {order['purpose']}
📅 {order['jalali_date']} | وضعیت: {order.get('status_text', 'در انتظار بررسی')}
{'─' * 40}
"""
        return formatted_orders
    except FileNotFoundError:
        return "هیچ سفارشی ثبت نشده است."

def delete_order(order_id):
    # Delete from text file
    try:
        with open(ORDER_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(ORDER_FILE, "w", encoding="utf-8") as f:
            skip = False
            for line in lines:
                if line.startswith(f"OrderID: {order_id}"):
                    skip = True
                elif line.startswith("="*50):
                    skip = False
                if not skip:
                    f.write(line)
    except FileNotFoundError:
        pass
    
    # Delete from JSON
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            orders = json.load(f)
        orders = [o for o in orders if o['order_id'] != order_id]
        with open(ORDERS_JSON, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

def delete_old_orders():
    """Delete orders older than specified date"""
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            orders = json.load(f)
        return orders
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_order_stats():
    """Get order statistics"""
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            orders = json.load(f)
        
        total = len(orders)
        today = jdatetime.now().strftime("%Y/%m/%d")
        today_orders = len([o for o in orders if o.get('jalali_date', '').startswith(today)])
        
        status_count = {}
        for order in orders:
            status = order.get('status', 'pending')
            status_count[status] = status_count.get(status, 0) + 1
        
        return {
            'total': total,
            'today': today_orders,
            'pending': status_count.get('pending', 0),
            'priced': status_count.get('priced', 0),
            'completed': status_count.get('completed', 0),
            'rejected': status_count.get('rejected', 0)
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {'total': 0, 'today': 0, 'pending': 0, 'priced': 0, 'completed': 0, 'rejected': 0}

def update_order_status(order_id, status, status_text):
    """Update order status in JSON file"""
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            orders = json.load(f)
        
        for order in orders:
            if order['order_id'] == order_id:
                order['status'] = status
                order['status_text'] = status_text
                break
        
        with open(ORDERS_JSON, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

def validate_phone(phone):
    phone = phone.strip().replace(" ", "").replace("-", "")
    pattern = r'^(\+98|0098|98|0)?9\d{9}$'
    return bool(re.match(pattern, phone))

def validate_email(email):
    if email.strip() == "." or email.strip() == "":
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def create_glass_keyboard(buttons_data):
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

def get_user_info(chat_id):
    """Get user information including username"""
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getChat",
            params={"chat_id": chat_id}
        )
        data = response.json()
        if data.get("ok"):
            user_info = data.get("result", {})
            username = user_info.get("username", "")
            first_name = user_info.get("first_name", "")
            last_name = user_info.get("last_name", "")
            return {
                "username": f"@{username}" if username else "ندارد",
                "full_name": f"{first_name} {last_name}".strip()
            }
    except:
        pass
    return {"username": "ندارد", "full_name": "نامشخص"}

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
    return create_glass_keyboard([
        [{"text": "🚫 لغو سفارش", "callback": "cancel_order"}]
    ])

def get_edit_keyboard():
    return create_glass_keyboard([
        [{"text": "✏️ ویرایش", "callback": "edit_order"}, {"text": "✅ تأیید و ارسال", "callback": "confirm_yes"}],
        [{"text": "❌ لغو سفارش", "callback": "confirm_no"}]
    ])

def get_edit_field_keyboard():
    return create_glass_keyboard([
        [{"text": "👤 نام", "callback": "edit_name"}, {"text": "📱 شماره", "callback": "edit_phone"}],
        [{"text": "📧 ایمیل", "callback": "edit_email"}, {"text": "💼 کسب‌وکار", "callback": "edit_business"}],
        [{"text": "🎯 هدف", "callback": "edit_purpose"}, {"text": "⚡ ویژگی‌ها", "callback": "edit_features"}],
        [{"text": "🌐 دامنه", "callback": "edit_domain"}, {"text": "📝 توضیحات", "callback": "edit_extra"}],
        [{"text": "🛠 پشتیبانی", "callback": "edit_support"}],
        [{"text": "🔙 بازگشت", "callback": "back_to_confirm"}]
    ])

def get_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "🏠 شروع مجدد"}, {"text": "🔍 پیگیری سفارش"}],
            [{"text": "🚫 لغو سفارش"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_admin_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "📋 مشاهده سفارشات"}, {"text": "📊 آمار سفارشات"}],
            [{"text": "💰 اعلام قیمت"}, {"text": "❌ رد سفارش"}],
            [{"text": "🗑 حذف سفارشات قدیمی"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_orders_selection_keyboard():
    keyboard_data = []
    active_orders = []
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            orders = json.load(f)
        
        for order in orders:
            if order.get("status", "pending") in ["pending", "priced"]:
                order_id = order["order_id"]
                customer_name = order.get("name", "نامشخص")
                status_emoji = "⏳" if order.get("status") == "pending" else "💰"
                active_orders.append({
                    "text": f"{status_emoji} {order_id} - {customer_name}",
                    "callback": f"select_order_{order_id}"
                })
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    for i in range(0, len(active_orders), 1):
        row = active_orders[i:i+1]
        keyboard_data.append(row)
    
    if not keyboard_data:
        keyboard_data.append([{"text": "❌ سفارش فعالی وجود ندارد", "callback": "no_orders"}])
    return create_glass_keyboard(keyboard_data)

def get_delete_options_keyboard():
    return create_glass_keyboard([
        [{"text": "🗑 حذف سفارشات 30 روز گذشته", "callback": "delete_30_days"}],
        [{"text": "🗑 حذف سفارشات 60 روز گذشته", "callback": "delete_60_days"}],
        [{"text": "🗑 حذف سفارشات تکمیل شده", "callback": "delete_completed"}],
        [{"text": "🗑 حذف سفارشات رد شده", "callback": "delete_rejected"}],
        [{"text": "🔙 بازگشت", "callback": "back_admin_menu"}]
    ])

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
    if chat_id == ADMIN_CHAT_ID:
        return handle_admin_message(chat_id, text)
    return handle_user_message(chat_id, text, message)

def handle_callback_query(callback_query):
    chat_id = str(callback_query["from"]["id"])
    callback_data = callback_query["data"]
    message_id = callback_query["message"]["message_id"]
    callback_query_id = callback_query["id"]
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
    
    elif callback_data.startswith("delete_"):
        if callback_data == "delete_30_days":
            # Implementation for deleting 30 days old orders
            pass
        elif callback_data == "delete_60_days":
            # Implementation for deleting 60 days old orders
            pass
        elif callback_data == "delete_completed":
            # Delete completed orders
            pass
        elif callback_data == "delete_rejected":
            # Delete rejected orders
            pass
    
    elif callback_data == "no_orders":
        edit_message(chat_id, message_id, "❌ <b>هیچ سفارش فعالی وجود ندارد!</b>", get_admin_menu_keyboard())
    
    elif callback_data == "back_admin_menu":
        edit_message(chat_id, message_id, "👨‍💼 <b>پنل مدیریت:</b>", get_admin_menu_keyboard())
    
    return {"ok": True}

def handle_user_callback(chat_id, callback_data, message_id):
    sess = sessions.get(chat_id, {})
    
    if callback_data == "cancel_order":
        edit_message(chat_id, message_id, "❌ <b>سفارش لغو شد.</b>\nبرای شروع مجدد /start را ارسال کنید.")
        sessions.pop(chat_id, None)
        return {"ok": True}
    
    if callback_data == "edit_order":
        edit_message(chat_id, message_id, "<b>✏️ کدام قسمت را می‌خواهید ویرایش کنید؟</b>", get_edit_field_keyboard())
        sess["editing"] = True
        sessions[chat_id] = sess
        return {"ok": True}
    
    if callback_data.startswith("edit_"):
        field = callback_data.replace("edit_", "")
        field_names = {
            "name": "نام", "phone": "شماره تماس", "email": "ایمیل",
            "business": "نوع کسب‌وکار", "purpose": "هدف", "features": "ویژگی‌ها",
            "domain": "دامنه/هاست", "extra": "توضیحات", "support": "پشتیبانی"
        }
        edit_message(chat_id, message_id, f"<b>✏️ {field_names[field]} جدید را وارد کنید:</b>", get_cancel_keyboard())
        sess["editing_field"] = field
        sessions[chat_id] = sess
        return {"ok": True}
    
    if callback_data == "back_to_confirm":
        order_id = sess.get("order_id", "ORD-" + uuid.uuid4().hex[:8].upper())
        sess["order_id"] = order_id
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
🛠 <b>پشتیبانی:</b> {sess.get('support', '')}
        """
        edit_message(chat_id, message_id, f"<b>📋 لطفاً اطلاعات را بررسی کنید:</b>{summary}", get_edit_keyboard())
        sess["step"] = "confirm"
        sess.pop("editing", None)
        sess.pop("editing_field", None)
        sessions[chat_id] = sess
        return {"ok": True}
    
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
    
    elif callback_data.startswith("domain_"):
        answer = "بله" if callback_data == "domain_yes" else "خیر"
        sess["domain"] = answer
        sess["step"] = "extra"
        edit_message(chat_id, message_id, "📝 <b>توضیحات تکمیلی (اختیاری):</b>\n<i>هر چیزی که فکر می‌کنید باید بدانیم یا نقطه برای رد کردن</i>", get_cancel_keyboard())
        sessions[chat_id] = sess
    
    elif callback_data.startswith("support_"):
        answer = "بله" if callback_data == "support_yes" else "خیر"
        sess["support"] = answer
        
        # اضافه کردن پیام پشتیبانی
        support_message = ""
        if answer == "بله":
            support_message = "\n\n🛠 <b>توجه:</b> دو ماه اول پشتیبانی رایگان است و از ماه سوم به بعد پشتیبانی به عهده شما خواهد بود. قرارداد ما سالیانه است."
        
        order_id = sess.get("order_id", "ORD-" + uuid.uuid4().hex[:8].upper())
        sess["order_id"] = order_id
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
🛠 <b>پشتیبانی:</b> {answer}{support_message}
        """
        edit_message(chat_id, message_id, f"<b>📋 لطفاً اطلاعات را بررسی کنید:</b>{summary}", get_edit_keyboard())
        sess["step"] = "confirm"
        sessions[chat_id] = sess
    
    elif callback_data == "confirm_yes":
        # Get user info including username
        user_info = get_user_info(chat_id)
        jalali_date = jdatetime.now().strftime("%Y/%m/%d %H:%M:%S")
        
        order_text = f"""
OrderID: {sess.get('order_id', '')}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Jalali Date: {jalali_date}
Name: {sess.get('name', '')}
Phone: {sess.get('phone', '')}
Email: {sess.get('email', '')}
Telegram Username: {user_info['username']}
Business Type: {sess.get('business', '')}
Website Purpose: {sess.get('purpose', '')}
Features: {sess.get('features', '')}
Has Domain/Host: {sess.get('domain', '')}
Extra Info: {sess.get('extra', '')}
Support: {sess.get('support', '')}
Chat ID: {chat_id}
Status: pending
        """
        
        order_data = {
            'order_id': sess.get('order_id', ''),
            'date': datetime.now().isoformat(),
            'jalali_date': jalali_date,
            'name': sess.get('name', ''),
            'phone': sess.get('phone', ''),
            'email': sess.get('email', ''),
            'telegram_username': user_info['username'],
            'business': sess.get('business', ''),
            'purpose': sess.get('purpose', ''),
            'features': sess.get('features', ''),
            'domain': sess.get('domain', ''),
            'extra': sess.get('extra', ''),
            'support': sess.get('support', ''),
            'chat_id': chat_id,
            'status': 'pending',
            'status_text': 'در انتظار بررسی'
        }
        
        save_order(order_text, order_data)
        
        # زیباتر کردن پیام ادمین
        admin_text = f"""
🆕 <b>سفارش جدید دریافت شد!</b>

🔖 <b>شناسه:</b> <code>{sess.get('order_id', '')}</code>
📅 <b>تاریخ:</b> {jalali_date}

👤 <b>اطلاعات مشتری:</b>
├ نام: {sess.get('name', '')}
├ تلگرام: {user_info['username']}
├ شماره: {sess.get('phone', '')}
└ ایمیل: {sess.get('email', 'ندارد')}

💼 <b>جزئیات پروژه:</b>
├ کسب‌وکار: {sess.get('business', '')}
├ هدف: {sess.get('purpose', '')}
├ ویژگی‌ها: {sess.get('features', '')}
├ دامنه/هاست: {sess.get('domain', '')}
├ پشتیبانی: {sess.get('support', '')}
└ توضیحات: {sess.get('extra', 'ندارد')}

🔗 <b>Chat ID:</b> <code>{chat_id}</code>
        """
        
        send_message(ADMIN_CHAT_ID, admin_text)
        
        edit_message(chat_id, message_id, f"""
✅ <b>سفارش شما با موفقیت ثبت شد!</b>

🔖 <b>شناسه سفارش:</b> <code>{sess.get('order_id', '')}</code>

⏳ کارشناسان ما در حال بررسی درخواست شما هستند و به زودی قیمت اعلام خواهد شد.

📞 در صورت نیاز با پشتیبانی تماس بگیرید.

💡 <b>نکته:</b> با استفاده از دکمه "🔍 پیگیری سفارش" می‌توانید وضعیت سفارش خود را پیگیری کنید.
        """)
        
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
    
    elif text == "📋 مشاهده سفارشات":
        orders = read_orders()
        send_message(chat_id, orders, get_admin_menu_keyboard())
        return {"ok": True}
    
    elif text == "📊 آمار سفارشات":
        stats = get_order_stats()
        stats_text = f"""
📊 <b>آمار سفارشات:</b>

📈 <b>کل سفارشات:</b> {stats['total']}
📅 <b>سفارشات امروز:</b> {stats['today']}

📊 <b>بر اساس وضعیت:</b>
├ ⏳ در انتظار: {stats['pending']}
├ 💰 قیمت اعلام شده: {stats['priced']}
├ ✅ تکمیل شده: {stats['completed']}
└ ❌ رد شده: {stats['rejected']}
        """
        send_message(chat_id, stats_text, get_admin_menu_keyboard())
        return {"ok": True}
    
    elif text == "💰 اعلام قیمت":
        send_message(chat_id, "<b>💰 انتخاب سفارش برای اعلام قیمت:</b>", get_orders_selection_keyboard())
        sessions[chat_id] = {"admin_action": "price"}
        return {"ok": True}
    
    elif text == "❌ رد سفارش":
        send_message(chat_id, "<b>❌ انتخاب سفارش برای رد:</b>", get_orders_selection_keyboard())
        sessions[chat_id] = {"admin_action": "reject"}
        return {"ok": True}
    
    elif text == "🗑 حذف سفارشات قدیمی":
        send_message(chat_id, "<b>🗑 انتخاب نوع حذف:</b>", get_delete_options_keyboard())
        return {"ok": True}
    
    # Handle price input
    if admin_sess.get("step") == "waiting_price":
        try:
            price = int(text.replace(",", "").replace("تومان", "").strip())
            order_id = admin_sess["selected_order"]
            
            # Find target customer
            target_chat_id = None
            target_name = None
            try:
                with open(ORDERS_JSON, "r", encoding="utf-8") as f:
                    orders = json.load(f)
                for order in orders:
                    if order['order_id'] == order_id:
                        target_chat_id = order['chat_id']
                        target_name = order['name']
                        break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            
            if target_chat_id:
                customer_message = f"""
💰 <b>سلام {target_name} عزیز!</b>

✨ قیمت پروژه شما <b>{price:,} تومان</b> برآورد شده است.

📞 برای هماهنگی بیشتر و شروع پروژه لطفاً با <a href='https://t.me/KHOFNAKA'>@KHOFNAKA</a> تماس بگیرید.

🔖 <b>شناسه سفارش:</b> <code>{order_id}</code>
                """
                send_message(target_chat_id, customer_message)
                
                # Update order status
                update_order_status(order_id, "priced", f"قیمت اعلام شده: {price:,} تومان")
                
                send_message(chat_id, f"✅ <b>قیمت با موفقیت اعلام شد!</b>\n\n💰 مبلغ: <b>{price:,} تومان</b>\n🔖 سفارش: <code>{order_id}</code>", get_admin_menu_keyboard())
            else:
                send_message(chat_id, "❌ <b>خطا:</b> سفارش یافت نشد!", get_admin_menu_keyboard())
            
            sessions.pop(chat_id, None)
        except ValueError:
            send_message(chat_id, "❌ <b>خطا:</b> لطفاً مبلغ را به عدد وارد کنید!")
    
    # Handle rejection reason
    elif admin_sess.get("step") == "waiting_reason":
        reason = text.strip()
        order_id = admin_sess["selected_order"]
        
        # Find target customer
        target_chat_id = None
        target_name = None
        try:
            with open(ORDERS_JSON, "r", encoding="utf-8") as f:
                orders = json.load(f)
            for order in orders:
                if order['order_id'] == order_id:
                    target_chat_id = order['chat_id']
                    target_name = order['name']
                    break
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        if target_chat_id:
            customer_message = f"""
❌ <b>مشتری عزیز {target_name}</b>

متأسفانه درخواست شما بررسی شد و به دلیل <b>{reason}</b> امکان همکاری فراهم نیست.

🙏 از صبوری و درک شما سپاسگزاریم.

🔖 <b>شناسه سفارش:</b> <code>{order_id}</code>
            """
            send_message(target_chat_id, customer_message)
            
            # Update order status
            update_order_status(order_id, "rejected", f"رد شده: {reason}")
            
            send_message(chat_id, f"✅ <b>سفارش با موفقیت رد شد!</b>\n\n🔖 سفارش: <code>{order_id}</code>\n📝 دلیل: {reason}", get_admin_menu_keyboard())
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
    
    elif text == "🔍 پیگیری سفارش":
        send_message(chat_id, "🔍 <b>لطفاً شناسه سفارش خود را وارد کنید:</b>\n<i>(مثال: ORD-A1B2C3D4)</i>", get_menu_keyboard())
        sessions[chat_id] = {"step": "track_order"}
        return {"ok": True}
    
    elif text == "🚫 لغو سفارش":
        send_message(chat_id, "❌ <b>سفارش لغو شد.</b>\nبرای شروع مجدد 'شروع مجدد' را انتخاب کنید.", get_menu_keyboard())
        sessions.pop(chat_id, None)
        return {"ok": True}
    
    sess = sessions.get(chat_id)
    if not sess:
        send_message(chat_id, "🔄 <b>لطفاً ابتدا 'شروع مجدد' را انتخاب کنید.</b>", get_menu_keyboard())
        return {"ok": True}
    
    step = sess["step"]
    
    # Handle order tracking
    if step == "track_order":
        order_id = text.strip().upper()
        try:
            with open(ORDERS_JSON, "r", encoding="utf-8") as f:
                orders = json.load(f)
            
            found_order = None
            for order in orders:
                if order['order_id'] == order_id and order['chat_id'] == chat_id:
                    found_order = order
                    break
            
            if found_order:
                status_emoji = {
                    "pending": "⏳",
                    "priced": "💰", 
                    "completed": "✅",
                    "rejected": "❌"
                }
                emoji = status_emoji.get(found_order.get("status", "pending"), "⏳")
                
                track_text = f"""
🔍 <b>وضعیت سفارش شما:</b>

🔖 <b>شناسه:</b> <code>{found_order['order_id']}</code>
📅 <b>تاریخ ثبت:</b> {found_order.get('jalali_date', '')}
{emoji} <b>وضعیت:</b> {found_order.get('status_text', 'در انتظار بررسی')}

👤 <b>نام:</b> {found_order['name']}
💼 <b>کسب‌وکار:</b> {found_order['business']}
🎯 <b>هدف:</b> {found_order['purpose']}
                """
                send_message(chat_id, track_text, get_menu_keyboard())
            else:
                send_message(chat_id, "❌ <b>سفارش یافت نشد!</b>\nلطفاً شناسه سفارش را بررسی کنید یا با پشتیبانی تماس بگیرید.", get_menu_keyboard())
        except (FileNotFoundError, json.JSONDecodeError):
            send_message(chat_id, "❌ <b>خطا در دسترسی به اطلاعات!</b>\nلطفاً دوباره تلاش کنید.", get_menu_keyboard())
        
        sessions.pop(chat_id, None)
        return {"ok": True}
    
    # Handle editing fields
    if sess.get("editing_field"):
        field = sess["editing_field"]
        new_value = text.strip()
        
        # Validate input based on field type
        if field == "phone" and not validate_phone(new_value):
            send_message(chat_id, "❌ <b>شماره تلفن نامعتبر است!</b>\nلطفاً شماره معتبر وارد کنید:", get_cancel_keyboard())
            return {"ok": True}
        elif field == "email" and not validate_email(new_value):
            send_message(chat_id, "❌ <b>ایمیل نامعتبر است!</b>\nلطفاً ایمیل معتبر وارد کنید یا برای رد کردن نقطه بگذارید:", get_cancel_keyboard())
            return {"ok": True}
        elif field == "name" and len(new_value) < 2:
            send_message(chat_id, "❌ <b>نام وارد شده کوتاه است!</b>\nلطفاً نام کامل خود را وارد کنید:", get_cancel_keyboard())
            return {"ok": True}
        
        # Special handling for email field
        if field == "email" and new_value == ".":
            new_value = ""
        
        # Update the field
        sess[field] = new_value
        
        # Show confirmation message
        field_names = {
            "name": "نام", "phone": "شماره تماس", "email": "ایمیل",
            "business": "نوع کسب‌وکار", "purpose": "هدف", "features": "ویژگی‌ها",
            "domain": "دامنه/هاست", "extra": "توضیحات", "support": "پشتیبانی"
        }
        
        send_message(chat_id, f"✅ <b>{field_names[field]} با موفقیت به‌روزرسانی شد!</b>\n\n🔙 بازگشت به صفحه تأیید...", get_cancel_keyboard())
        
        # Return to confirmation
        order_id = sess.get("order_id", "ORD-" + uuid.uuid4().hex[:8].upper())
        sess["order_id"] = order_id
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
🛠 <b>پشتیبانی:</b> {sess.get('support', '')}
        """
        
        send_message(chat_id, f"<b>📋 لطفاً اطلاعات را بررسی کنید:</b>{summary}", get_edit_keyboard())
        sess["step"] = "confirm"
        sess.pop("editing_field", None)
        sessions[chat_id] = sess
        return {"ok": True}
    
    # Original form steps
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
