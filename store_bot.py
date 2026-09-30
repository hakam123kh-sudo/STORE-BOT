# -*- coding: utf-8 -*-
"""
بوت مبيعات «مدير السوشيال ميديا بالذكاء الاصطناعي»
--------------------------------------------------
بيع شبه-تلقائي:
  1) الزبون يفتح البوت → يشوف الكتاب والسعر → يضغط «اطلب الكتاب».
  2) البوت يعطيه تعليمات التحويل (حسابك المصرفي) ويطلب صورة إثبات التحويل.
  3) الزبون يرسل الصورة → توصلك أنت (المالك) مع زرّين: ✅ قبول / ❌ رفض.
  4) تضغط «✅ قبول» → البوت يرسل الكتاب والقوالب للزبون تلقائيًا. تضغط «❌ رفض» → يعتذر له بأدب.

يشتغل على جهازك (long polling). ملاحظة: يرد على الزبائن فقط وهو شغّال والجهاز مفتوح.
لتشغيله دائمًا (٢٤/٧) لازم يُستضاف على سيرفر — نساعدك في ذلك لاحقًا.

الإعداد: انسخ keys.example.json إلى keys.json واملأه (توكن البوت من @BotFather، رقم محادثتك، بيانات التحويل).
التشغيل: python store_bot.py   (أو شغّل Start-Store-Bot.bat)
"""

import json
import os
import time
import html
import requests

BASE = os.path.dirname(os.path.abspath(__file__))

def load_cfg():
    with open(os.path.join(BASE, "keys.json"), "r", encoding="utf-8") as f:
        return json.load(f)

CFG = load_cfg()
TOKEN = CFG["bot_token"]
OWNER = int(CFG["owner_chat_id"])
PRICE = CFG.get("price", "29.99$")
BANK = CFG.get("bank_info", "—")
BOOK_TITLE = CFG.get("book_title", "مدير السوشيال ميديا بالذكاء الاصطناعي")
FILES = CFG.get("files", [])            # قائمة مسارات الملفات التي تُرسل بعد القبول
API = f"https://api.telegram.org/bot{TOKEN}"

STATE_PATH = os.path.join(BASE, "orders.json")
def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"pending": {}, "delivered": []}
def save_state(s):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
STATE = load_state()

def api(method, **params):
    try:
        r = requests.post(f"{API}/{method}", json=params, timeout=40)
        return r.json()
    except Exception as e:
        print("[api]", method, e, flush=True)
        return {}

def send(chat, text, **extra):
    return api("sendMessage", chat_id=chat, text=text, parse_mode="HTML", **extra)

def send_document(chat, path, caption=None):
    try:
        with open(path, "rb") as fh:
            files = {"document": (os.path.basename(path), fh)}
            data = {"chat_id": chat}
            if caption:
                data["caption"] = caption
            r = requests.post(f"{API}/sendDocument", data=data, files=files, timeout=120)
            return r.json()
    except Exception as e:
        print("[sendDocument]", path, e, flush=True)
        return {}

def kb(rows):
    return {"inline_keyboard": rows}

WELCOME = (
    f"أهلاً بك! 📘\n\n"
    f"<b>{html.escape(BOOK_TITLE)}</b>\n"
    f"دليل عملي يعلّمك إدارة صفحات السوشيال ميديا بالذكاء الاصطناعي — من الصفر إلى أول عميل.\n\n"
    f"يشمل: الكتاب (PDF) + قالب جدول المحتوى (Excel) + نماذج رسائل العملاء.\n\n"
    f"💰 السعر: <b>{html.escape(str(PRICE))}</b>\n\n"
    f"اضغط الزر بالأسفل للطلب."
)

def pay_instructions():
    return (
        "🧾 <b>خطوات الطلب</b>\n\n"
        f"1) حوّل قيمة الكتاب ({html.escape(str(PRICE))}) على:\n{html.escape(str(BANK))}\n\n"
        "2) صوّر إثبات التحويل وأرسله هنا كصورة.\n\n"
        "3) بعد التأكيد يوصلك الكتاب والقوالب مباشرة. ⏳"
    )

def handle_message(msg):
    chat = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    # المالك: أوامر بسيطة
    if chat == OWNER and text.startswith("/orders"):
        p = STATE["pending"]
        if not p:
            send(OWNER, "لا توجد طلبات معلّقة.")
        else:
            send(OWNER, "طلبات معلّقة:\n" + "\n".join(f"- {u}" for u in p))
        return

    if text.startswith("/start") or text in ("ابدأ", "بدء"):
        send(chat, WELCOME, reply_markup=kb([[{"text": "🛒 اطلب الكتاب", "callback_data": "order"}]]))
        return

    # صورة (إثبات تحويل)
    if "photo" in msg or "document" in msg:
        if str(chat) in STATE["pending"] and STATE["pending"][str(chat)].get("stage") == "await_proof":
            STATE["pending"][str(chat)]["stage"] = "review"
            save_state(STATE)
            name = msg["chat"].get("first_name", "زبون")
            uname = msg["chat"].get("username", "")
            # حوّل الإثبات للمالك
            if "photo" in msg:
                fid = msg["photo"][-1]["file_id"]
                api("sendPhoto", chat_id=OWNER, photo=fid,
                    caption=f"🧾 إثبات تحويل من <b>{html.escape(name)}</b> "
                            f"(@{html.escape(uname)} · <code>{chat}</code>)",
                    parse_mode="HTML",
                    reply_markup=kb([[{"text": "✅ قبول وإرسال الكتاب", "callback_data": f"ok:{chat}"},
                                      {"text": "❌ رفض", "callback_data": f"no:{chat}"}]]))
            else:
                fid = msg["document"]["file_id"]
                api("sendDocument", chat_id=OWNER, document=fid,
                    caption=f"🧾 إثبات تحويل من {html.escape(name)} (<code>{chat}</code>)",
                    parse_mode="HTML",
                    reply_markup=kb([[{"text": "✅ قبول وإرسال الكتاب", "callback_data": f"ok:{chat}"},
                                      {"text": "❌ رفض", "callback_data": f"no:{chat}"}]]))
            send(chat, "✅ استلمنا إثبات التحويل، جاري المراجعة. يوصلك الكتاب حال التأكيد. شكرًا لصبرك 🌟")
        else:
            send(chat, "لطلب الكتاب اضغط /start ثم «اطلب الكتاب».")
        return

    # نص عام
    send(chat, "لطلب الكتاب اضغط /start.")

def handle_callback(cq):
    data = cq.get("data", "")
    frm = cq["from"]["id"]
    api("answerCallbackQuery", callback_query_id=cq["id"])

    if data == "order":
        STATE["pending"][str(frm)] = {"stage": "await_proof", "ts": time.time()}
        save_state(STATE)
        send(frm, pay_instructions())
        return

    # أزرار المالك
    if data.startswith("ok:") or data.startswith("no:"):
        if frm != OWNER:
            return
        cust = data.split(":", 1)[1]
        if data.startswith("ok:"):
            send(cust, "🎉 تم تأكيد طلبك! هذا كتابك وقوالبك، بالتوفيق:")
            sent = 0
            for path in FILES:
                if os.path.exists(path):
                    r = send_document(cust, path)
                    if r.get("ok"):
                        sent += 1
                else:
                    print("[missing file]", path, flush=True)
            send(cust, "📌 نماذج رسائل العملاء داخل الكتاب (الملحق أ). لو احتجت أي مساعدة راسلنا.")
            STATE["pending"].pop(cust, None)
            STATE["delivered"].append({"chat": cust, "ts": time.time()})
            save_state(STATE)
            send(OWNER, f"✅ تم إرسال {sent} ملف للزبون <code>{cust}</code>.")
        else:
            send(cust, "عذرًا، لم نتمكن من تأكيد التحويل بعد. تأكد من الإرسال أو راسلنا للمساعدة 🙏")
            STATE["pending"].pop(cust, None)
            save_state(STATE)
            send(OWNER, f"❌ تم رفض طلب <code>{cust}</code>.")
        return

def main():
    print("Store bot running…", flush=True)
    # تأكد أن الملفات موجودة
    for pth in FILES:
        print(("✔" if os.path.exists(pth) else "✘ مفقود"), pth, flush=True)
    offset = None
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"timeout": 30, "offset": offset,
                                     "allowed_updates": json.dumps(["message", "callback_query"])},
                             timeout=40).json()
        except Exception as e:
            print("[poll]", e, flush=True); time.sleep(3); continue
        for up in r.get("result", []):
            offset = up["update_id"] + 1
            try:
                if "message" in up:
                    handle_message(up["message"])
                elif "callback_query" in up:
                    handle_callback(up["callback_query"])
            except Exception as e:
                print("[handle]", e, flush=True)

if __name__ == "__main__":
    main()
