# -*- coding: utf-8 -*-
"""
بوت مبيعات «مدير السوشيال ميديا بالذكاء الاصطناعي» — نسخة الاستضافة (24/7)
يقرأ الإعداد من متغيّرات البيئة (Environment Variables) أو من keys.json،
ويرسل كل الملفات الموجودة داخل مجلد files/ بعد قبولك للطلب.
"""
import os, json, time, glob, html, requests

BASE = os.path.dirname(os.path.abspath(__file__))

def _cfg():
    data = {}
    try:
        with open(os.path.join(BASE, "keys.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    envmap = {"bot_token": "BOT_TOKEN", "owner_chat_id": "OWNER_CHAT_ID",
              "price": "PRICE", "bank_info": "BANK_INFO", "book_title": "BOOK_TITLE"}
    for k, e in envmap.items():
        v = os.environ.get(e)
        if v:
            data[k] = v
    return data

CFG = _cfg()
TOKEN = CFG["bot_token"]
OWNER = int(CFG["owner_chat_id"])
PRICE = CFG.get("price", "29.99$")
BANK = CFG.get("bank_info", "—")
BOOK_TITLE = CFG.get("book_title", "مدير السوشيال ميديا بالذكاء الاصطناعي")
FILES = sorted(glob.glob(os.path.join(BASE, "files", "*")))
API = f"https://api.telegram.org/bot{TOKEN}"

STATE_PATH = os.path.join(BASE, "orders.json")
def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"pending": {}, "delivered": []}
def save_state(s):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[state]", e, flush=True)
STATE = load_state()

def api(method, **params):
    try:
        return requests.post(f"{API}/{method}", json=params, timeout=40).json()
    except Exception as e:
        print("[api]", method, e, flush=True); return {}

def send(chat, text, **extra):
    return api("sendMessage", chat_id=chat, text=text, parse_mode="HTML", **extra)

def send_document(chat, path, caption=None):
    try:
        with open(path, "rb") as fh:
            data = {"chat_id": chat}
            if caption:
                data["caption"] = caption
            return requests.post(f"{API}/sendDocument", data=data,
                                 files={"document": (os.path.basename(path), fh)}, timeout=120).json()
    except Exception as e:
        print("[sendDocument]", path, e, flush=True); return {}

def kb(rows):
    return {"inline_keyboard": rows}

WELCOME = (
    f"أهلاً بك! 📘\n\n<b>{html.escape(BOOK_TITLE)}</b>\n"
    "دليل عملي يعلّمك إدارة صفحات السوشيال ميديا بالذكاء الاصطناعي — من الصفر إلى أول عميل.\n\n"
    "يشمل: الكتاب (PDF) + قالب جدول المحتوى (Excel) + نماذج رسائل العملاء.\n\n"
    f"💰 السعر: <b>{html.escape(str(PRICE))}</b>\n\nاضغط الزر بالأسفل للطلب."
)

def pay_instructions():
    return ("🧾 <b>خطوات الطلب</b>\n\n"
            f"1) حوّل قيمة الكتاب على:\n{html.escape(str(BANK))}\n\n"
            "2) صوّر إثبات التحويل وأرسله هنا كصورة.\n\n"
            "3) بعد التأكيد يوصلك الكتاب والقوالب مباشرة. ⏳")

def handle_message(msg):
    chat = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if chat == OWNER and text.startswith("/orders"):
        p = STATE["pending"]
        send(OWNER, "لا توجد طلبات معلّقة." if not p else "طلبات معلّقة:\n" + "\n".join(f"- {u}" for u in p))
        return
    if text.startswith("/start") or text in ("ابدأ", "بدء"):
        send(chat, WELCOME, reply_markup=kb([[{"text": "🛒 اطلب الكتاب", "callback_data": "order"}]])); return
    if "photo" in msg or "document" in msg:
        if str(chat) in STATE["pending"] and STATE["pending"][str(chat)].get("stage") == "await_proof":
            STATE["pending"][str(chat)]["stage"] = "review"; save_state(STATE)
            name = msg["chat"].get("first_name", "زبون"); uname = msg["chat"].get("username", "")
            btns = kb([[{"text": "✅ قبول وإرسال الكتاب", "callback_data": f"ok:{chat}"},
                       {"text": "❌ رفض", "callback_data": f"no:{chat}"}]])
            if "photo" in msg:
                api("sendPhoto", chat_id=OWNER, photo=msg["photo"][-1]["file_id"],
                    caption=f"🧾 إثبات تحويل من <b>{html.escape(name)}</b> (@{html.escape(uname)} · <code>{chat}</code>)",
                    parse_mode="HTML", reply_markup=btns)
            else:
                api("sendDocument", chat_id=OWNER, document=msg["document"]["file_id"],
                    caption=f"🧾 إثبات تحويل من {html.escape(name)} (<code>{chat}</code>)",
                    parse_mode="HTML", reply_markup=btns)
            send(chat, "✅ استلمنا إثبات التحويل، جاري المراجعة. يوصلك الكتاب حال التأكيد. شكرًا 🌟")
        else:
            send(chat, "لطلب الكتاب اضغط /start ثم «اطلب الكتاب».")
        return
    send(chat, "لطلب الكتاب اضغط /start.")

def handle_callback(cq):
    data = cq.get("data", ""); frm = cq["from"]["id"]
    api("answerCallbackQuery", callback_query_id=cq["id"])
    if data == "order":
        STATE["pending"][str(frm)] = {"stage": "await_proof", "ts": time.time()}; save_state(STATE)
        send(frm, pay_instructions()); return
    if data.startswith("ok:") or data.startswith("no:"):
        if frm != OWNER:
            return
        cust = data.split(":", 1)[1]
        if data.startswith("ok:"):
            send(cust, "🎉 تم تأكيد طلبك! هذا كتابك وقوالبك، بالتوفيق:")
            sent = 0
            for path in FILES:
                if os.path.exists(path) and send_document(cust, path).get("ok"):
                    sent += 1
            send(cust, "📌 نماذج رسائل العملاء داخل الكتاب (الملحق أ). لأي مساعدة راسلنا.")
            STATE["pending"].pop(cust, None); STATE["delivered"].append({"chat": cust, "ts": time.time()}); save_state(STATE)
            send(OWNER, f"✅ تم إرسال {sent} ملف للزبون <code>{cust}</code>.")
        else:
            send(cust, "عذرًا، لم نتمكن من تأكيد التحويل بعد. تأكد من الإرسال أو راسلنا 🙏")
            STATE["pending"].pop(cust, None); save_state(STATE)
            send(OWNER, f"❌ تم رفض طلب <code>{cust}</code>.")
        return

def main():
    print("Store bot (hosted) running…", flush=True)
    print("files:", [os.path.basename(f) for f in FILES], flush=True)
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
