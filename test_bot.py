#!/usr/bin/env python3
"""Self-check for stage 1. Consumers: run by hand before every deploy: python3 test_bot.py"""
from bot import classify

CASES = [
    # real spam from the group, 2026-11
    ("来码洗米 挣八千", "沐荞", "spam"),
    ("来人帮我洗钱简单一天3千", "包嵩", "spam"),
    ("全新国行水果手机 假1赔10  @jhvip0", "Ainalic Vale", "spam"),
    ("Vergütung von bis zu 2.800 € im Monat, schreib mir", "Lena", "spam"),
    ("Vergütung von bis zu 2.800€, schreib mir", "Lena", "spam"),  # no space before €
    ("Пишите в личку, оплата сразу", "Olga", "unsure"),  # Cyrillic: AI decides
    # unsure: AI decides
    ("Jetzt in Bitcoin investieren!", "Max", "unsure"),
    ("Ich geh morgen impfen, kommt wer mit?", "Anna", "unsure"),
    ("➡ Mehr Infos hier", "Max", "unsure"),  # without the emoji variation selector
    ("Mehr Infos⬇️", "Max", "unsure"),  # emoji glued to a word
    ("Привет всем, кто едет сегодня в центр?", "Olga", "unsure"),
    ("Artikel dazu: https://www.stuttgarter-zeitung.de/kontrollen", "Tom", "unsure"),
    ("Schau mal t.me/irgendwas", "Tom", "unsure"),
    ("Hallo zusammen", "王伟", "unsure"),
    # normal chat must stay
    ("Kontrolle U14 Hauptbahnhof Richtung Remseck", "Tom", "ok"),
    ("@Peter danke dir!", "Anna", "ok"),
    ("Hab mir einen Trademark-Kurs angeschaut", "Anna", "ok"),
    ("Kreditkarte geht am Automaten nicht", "Anna", "ok"),
    ("", "沐荞", "ok"),
]

failed = 0
for text, name, want in CASES:
    got, reason = classify(text, name)
    if got != want:
        failed += 1
        print(f"FAIL {text!r} ({name}): want {want}, got {got} ({reason})")
print(f"{len(CASES) - failed}/{len(CASES)} classify ok")

# handle(): delete on strike 1, ban on strike 2, admins untouched; Telegram API faked
import sqlite3
import bot

calls = []
bot.tg = lambda method, **p: calls.append(method) or ([{"user": {"id": 1}}] if method == "getChatAdministrators" else True)
bot.DRY_RUN, bot.STRIKES_TO_BAN, bot.REPORT_CHAT_ID = False, 2, ""
db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE strikes (chat_id INTEGER, user_id INTEGER, count INTEGER, PRIMARY KEY (chat_id, user_id))")
group = {"id": -100, "type": "supergroup"}
spam = {"chat": group, "from": {"id": 2, "first_name": "沐荞"}, "message_id": 5, "text": "来码洗米 挣八千"}
bot.handle(db, spam)
bot.handle(db, spam)
bot.handle(db, spam)  # burst message after the ban: deleted, no new strike
bot.handle(db, dict(spam, **{"from": {"id": 1, "first_name": "Admin"}}))
want = ["getChatAdministrators", "deleteMessage", "deleteMessage", "banChatMember", "deleteMessage"]
assert db.execute("SELECT COUNT(*) FROM strikes").fetchone()[0] == 0, "strike after ban"
if calls != want:
    failed += 1
    print(f"FAIL handle(): want {want}, got {calls}")
else:
    print("handle ok")

# test mode: report with two buttons, "Löschen" enforces, "Nicht löschen" and foreign chats do nothing
sent = []
bot.tg = lambda method, **p: sent.append((method, p)) or ([{"user": {"id": 1}}] if method == "getChatAdministrators" else True)
bot.DRY_RUN, bot.REPORT_CHAT_ID = True, "-5"
bot.handle(db, dict(spam, **{"from": {"id": 3, "first_name": "包嵩"}, "message_id": 9}))
buttons = [b["callback_data"] for b in sent[-1][1]["reply_markup"]["inline_keyboard"][0]]
report_msg = {"chat": {"id": -5}, "message_id": 77, "text": "🧪 Testmodus"}
tap = lambda data, chat=report_msg: bot.on_button(db, {"id": "q", "from": {"id": 1, "first_name": "Admin"}, "message": chat, "data": data})
sent.clear(); tap(buttons[1])
kept = [m for m, _ in sent] == ["answerCallbackQuery", "editMessageText"] and "Bleibt stehen" in sent[-1][1]["text"]
sent.clear(); tap(buttons[0], dict(report_msg, chat={"id": -6}))
foreign = [m for m, _ in sent] == ["answerCallbackQuery"]
sent.clear(); tap(buttons[0])
deleted = ("deleteMessage", {"chat_id": -100, "message_id": 9}) in sent and "Verwarnung 1/2" in sent[-1][1]["text"]
sent.clear(); tap(buttons[0]); tap(buttons[1])  # 2nd tap / 2nd admin: no 2nd strike, no "bleibt stehen"
deleted = deleted and "deleteMessage" not in [m for m, _ in sent] and all("Schon gelöscht" in p["text"] for m, p in sent if m == "editMessageText")
if buttons != ["d:-100:9:3", "k:-100:9:3"] or not (kept and foreign and deleted):
    failed += 1
    print(f"FAIL buttons: {buttons} kept={kept} foreign={foreign} deleted={deleted}")
else:
    print("buttons ok")
raise SystemExit(1 if failed else 0)
