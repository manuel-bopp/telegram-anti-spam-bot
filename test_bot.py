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
    ("Пишите в личку, оплата сразу", "Olga", "spam"),  # Rose words оплата / пишите
    # Rose list + categories (blocklist.txt since 2026-11-10): deleted
    ("Jetzt in Bitcoin investieren!", "Max", "spam"),
    ("Ich geh morgen impfen, kommt wer mit?", "Anna", "spam"),  # Rose deleted this too
    ("➡ Mehr Infos hier", "Max", "spam"),  # without the emoji variation selector
    ("Mehr Infos⬇️", "Max", "spam"),  # emoji glued to a word
    ("Artikel dazu: https://www.stuttgarter-zeitung.de/kontrollen", "Tom", "spam"),  # Rose: http*
    ("Schau mal t.me/irgendwas", "Tom", "spam"),
    ("Kokain und Gras, schreib mir privat", "Max", "spam"),
    ("Pistole zu verkaufen, Munition dabei", "Max", "spam"),
    ("Meine OnlyFans: hot pics 🔞", "Lisa", "spam"),
    ("Krypto-Trading mit 300% Gewinn", "Max", "spam"),
    # unsure: AI decides (left standing without a key)
    ("Привет всем, кто едет сегодня в центр?", "Olga", "unsure"),
    ("Hallo zusammen", "王伟", "unsure"),
    # normal chat must stay
    ("Kontrolle U14 Hauptbahnhof Richtung Remseck", "Tom", "ok"),
    ("@Peter danke dir!", "Anna", "ok"),
    ("Hab mir einen Trademark-Kurs angeschaut", "Anna", "ok"),
    ("Kreditkarte geht am Automaten nicht", "Anna", "ok"),
    ("Kontrolleure waren gewalttätig, Polizei ist da", "Tom", "ok"),
    ("Waffenverbotszone am Hbf, Polizei kontrolliert", "Tom", "ok"),
    ("Eine Frau wurde in der U2 sexuell belästigt", "Anna", "ok"),
    ("Gras am Schlossplatz ist frisch gemäht", "Anna", "ok"),
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
bot.handle(db, spam)  # the same message again (its edit): no 2nd strike, no API call
bot.handle(db, dict(spam, message_id=6))
bot.handle(db, dict(spam, message_id=7))  # burst message after the ban: deleted, no new strike
bot.handle(db, dict(spam, message_id=8, **{"from": {"id": 1, "first_name": "Admin"}}))
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

# live: card with Confirm / Revert / Block User; Revert unbans + re-posts, Block bans
bot.DRY_RUN = False
sent.clear(); bot.handle(db, dict(spam, **{"from": {"id": 4, "first_name": "Rebekah"}, "message_id": 11}))
card = sent[-1][1]
live_buttons = [b["callback_data"] for b in card["reply_markup"]["inline_keyboard"][0]]
card_ok = card["parse_mode"] == "HTML" and card["text"].startswith("<b>Spam gelöscht (Verwarnung 1/2)</b>") \
    and live_buttons == ["c:-100:11:4", "r:-100:11:4", "b:-100:11:4"]
plain = "Spam gelöscht (Verwarnung 1/2)\n👤 Rebekah (ID 4)\n🔎 Reason: chinesische Schrift\n💬 来码洗米 挣八千"
sent.clear(); tap("r:-100:11:4", dict(report_msg, text=plain))
reposted = [p for m, p in sent if m == "sendMessage"]
reverted = [m for m, _ in sent][:2] == ["answerCallbackQuery", "unbanChatMember"] and len(reposted) == 1 \
    and reposted[0]["chat_id"] == -100 and "Rebekah schrieb:\n来码洗米 挣八千" in reposted[0]["text"] \
    and db.execute("SELECT COUNT(*) FROM strikes WHERE user_id = 4").fetchone()[0] == 0
sent.clear(); tap("b:-100:11:4", dict(report_msg, text=plain))
blocked = ("banChatMember", {"chat_id": -100, "user_id": 4}) in sent and "gesperrt" in sent[-1][1]["text"]
if not (card_ok and reverted and blocked):
    failed += 1
    print(f"FAIL live card: card={card_ok} buttons={live_buttons} revert={reverted} block={blocked}")
else:
    print("live card ok")

# /block, /unblock in the report chat; extra patterns live next to the DB
import tempfile
from pathlib import Path
bot.EXTRA_PATH = Path(tempfile.mkdtemp()) / "blocklist-extra.txt"
admin_chat = {"id": -5, "type": "group"}
cmd = lambda t: bot.handle(db, {"chat": admin_chat, "from": {"id": 1}, "message_id": 1, "text": t})
cmd("/block casino*")
added = bot.classify("Bestes Casinoangebot", "x")[0] == "spam"
cmd("/unblock casino*")
removed = bot.classify("Bestes Casinoangebot", "x")[0] == "ok"
sent.clear(); cmd("/blocklist@freifahren_anti_spam_bot")
listed = "Feste Liste" in sent[-1][1]["text"]
if not (added and removed and listed):
    failed += 1
    print(f"FAIL commands: added={added} removed={removed} listed={listed}")
else:
    print("commands ok")
# join captcha: muted + greeted; a foreign tap does nothing, the joiner's tap unmutes; no tap = kicked
bot.CAPTCHA_MINUTES, bot.ALLOWED_CHATS = 5, {-100}
db.execute("CREATE TABLE pending (chat_id INTEGER, user_id INTEGER, msg_id INTEGER, deadline REAL, PRIMARY KEY (chat_id, user_id))")
bot.tg = lambda method, **p: sent.append((method, p)) or ({"message_id": 50} if method == "sendMessage" else {"permissions": {"can_send_messages": True}} if method == "getChat" else True)
sent.clear(); bot.handle(db, {"chat": group, "from": {"id": 7}, "message_id": 20, "new_chat_members": [{"id": 7, "first_name": "Neu"}]})
greeted = [m for m, _ in sent] == ["getChat", "restrictChatMember", "deleteMessage", "sendMessage"] and sent[1][1]["permissions"] == {"can_send_messages": False}
captcha = sent[-1][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
sent.clear(); bot.on_button(db, {"id": "q", "from": {"id": 8}, "message": {"chat": group}, "data": captcha})
foreign = [m for m, _ in sent] == ["answerCallbackQuery"]
sent.clear(); bot.on_button(db, {"id": "q", "from": {"id": 7}, "message": {"chat": group}, "data": captcha})
solved = ("restrictChatMember", {"chat_id": -100, "user_id": 7, "permissions": {"can_send_messages": True}}) in sent \
    and db.execute("SELECT COUNT(*) FROM pending").fetchone()[0] == 0
bot.on_member(db, {"chat": group, "old_chat_member": {"status": "left"}, "new_chat_member": {"status": "member", "user": {"id": 9}}})
db.execute("UPDATE pending SET deadline = 0")
sent.clear(); bot.sweep_captchas(db)
kicked = [m for m, _ in sent] == ["banChatMember", "deleteMessage"] and db.execute("SELECT COUNT(*) FROM pending").fetchone()[0] == 0
if not (greeted and foreign and solved and kicked):
    failed += 1
    print(f"FAIL captcha: greeted={greeted} foreign={foreign} solved={solved} kicked={kicked}")
else:
    print("captcha ok")
# bio check on join: Chinese bio = banned + card with Confirm / Revert (unban); a link-only bio passes
bot.CAPTCHA_MINUTES = 0
bios = {20: "https://t.me/+Dtsd7iG1ohExMGFl 有码进群私信老板了解 日入八千", 21: "https://t.me/meinkanal Fotografie", 22: "Привет, пишите мне"}
bot.tg = lambda method, **p: sent.append((method, p)) or ({"bio": bios.get(p.get("chat_id"), "")} if method == "getChat" else True)
sent.clear(); bot.handle(db, {"chat": group, "from": {"id": 20}, "message_id": 30, "new_chat_members": [{"id": 20, "first_name": "Tonia"}]})
methods = [m for m, _ in sent]
bio_card = sent[-1][1] if sent else {}
bio_banned = methods[:2] == ["getChat", "banChatMember"] and "deleteMessage" in methods \
    and [b["callback_data"] for b in bio_card["reply_markup"]["inline_keyboard"][0]] == ["c:-100:0:20", "u:-100:0:20"]
sent.clear(); bot.on_member(db, {"chat": group, "old_chat_member": {"status": "left"}, "new_chat_member": {"status": "member", "user": {"id": 20}}})
once = sent == []
sent.clear(); bot.on_member(db, {"chat": group, "old_chat_member": {"status": "left"}, "new_chat_member": {"status": "member", "user": {"id": 21}}})
link_ok = [m for m, _ in sent] == ["getChat"]
cyr = bot.bio_reason(bios[22]) == "kyrillische Schrift in der Bio"
sent.clear(); tap("u:-100:0:20")
unbanned = ("unbanChatMember", {"chat_id": -100, "user_id": 20, "only_if_banned": True}) in sent
if not (bio_banned and once and link_ok and cyr and unbanned):
    failed += 1
    print(f"FAIL bio: banned={bio_banned} once={once} link_ok={link_ok} cyr={cyr} unbanned={unbanned}")
else:
    print("bio ok")
raise SystemExit(1 if failed else 0)
