# Telegram Anti-Spam-Bot

Created: 2026-11-03 15:50 · claude-opus-5-5 · direct
Last updated: 2026-11-03 16:05 · claude-opus-5-5

Kleiner Bot, der Spam in Telegram-Gruppen löscht und Wiederholungstäter bannt. Gebaut für eine
Stuttgarter Gruppe, in der Rose die chinesischen Spam-Nachrichten nicht erwischt.

## Was er macht

1. **Stufe 1, Regeln** (`bot.py`, `classify()`):
   - Nachricht mehr als zur Hälfte in chinesischer Schrift: Spam.
   - Treffer in `blocklist.txt` (die zwei Jobangebot-Phrasen aus der bisherigen Rose-Liste): Spam.
   - Treffer in `suspicious.txt` (der Rest der Rose-Liste: Kredit, impfen, Bitcoin, оплата …,
     dazu Links und `$`),
     kyrillische Schrift, chinesischer Anzeigename: *unsicher*.
2. **Stufe 2, KI** (nur wenn `ANTHROPIC_API_KEY` gesetzt ist): Nur die *unsicheren*
   Nachrichten gehen an Claude Haiku, das mit SPAM oder OK antwortet. Ohne Schlüssel bleiben
   unsichere Nachrichten stehen. An die KI geht nur der Nachrichtentext, kein Name, keine ID.
3. Spam wird gelöscht und der Absender bekommt eine Verwarnung. Bei der 2. Verwarnung
   (`STRIKES_TO_BAN`) wird er dauerhaft gebannt. Seine älteren Nachrichten, die nicht als Spam
   erkannt wurden, bleiben stehen. Admins und Bots werden nie angefasst.
4. Jede Aktion geht als kurze Meldung an `REPORT_CHAT_ID` (den Admin).

**Testmodus** (`DRY_RUN=1`, Standard): löscht nichts, meldet nur, was er gelöscht hätte.

## Was er speichert und was nicht

- Gespeichert wird nur eine Tabelle `(Gruppen-ID, Nutzer-ID, Anzahl Verwarnungen)`.
  Nach einem Bann wird der Zähler gelöscht.
- Nachrichtentexte und Namen werden nicht gespeichert. Ein Auszug (max. 300 Zeichen) gelöschter
  Nachrichten steht nur in der Telegram-Meldung an den Admin. Das Systemprotokoll (journal)
  enthält nur Aktion, Grund, Gruppen-ID und Nutzer-ID.
- Eine Mitgliederliste kann der Bot gar nicht abrufen, das gibt die Telegram-Bot-API nicht her.
- Der Bot-Token gehört dem Gruppen-Admin. Mit `/revoke` beim @BotFather ist der Bot sofort tot.

## Rechte in der Gruppe

Als Admin hinzufügen, nur mit: **Nachrichten löschen** und **Nutzer sperren**. Sonst nichts.

## Installation (Linux mit systemd)

```bash
sudo git clone <repo-url> /opt/telegram-anti-spam-bot
cd /opt/telegram-anti-spam-bot
sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo cp env.example .env && sudo chmod 600 .env && sudo nano .env   # Token etc.
python3 test_bot.py                                                     # Selbsttest
sudo cp telegram-anti-spam-bot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now telegram-anti-spam-bot
journalctl -u telegram-anti-spam-bot -f
```

Die erste Testmodus-Meldung zeigt die Gruppen-ID. Die in `.env` bei `ALLOWED_CHAT_IDS` eintragen,
sonst arbeitet der Bot in jeder Gruppe, in die ihn jemand holt. Für einen Alarm, wenn der Dienst
dauerhaft ausfällt (z. B. widerrufener Token), in der Unit `OnFailure=` auf eine eigene
Alarm-Unit setzen.

Wenn die Testmodus-Meldungen ein paar Tage lang stimmen: in `.env` `DRY_RUN=0` setzen und den
Dienst neu starten.

## Anpassen

- Wörter: `blocklist.txt` (sofort löschen) oder `suspicious.txt` (KI entscheidet).
  Syntax wie bei Rose: ganzes Wort, `*` = beliebige Zeichen ohne Leerzeichen; ein Leerzeichen
  im Muster passt auch auf kein Leerzeichen („2.800€“).
- Nach jeder Änderung (auch an `.env`) `python3 test_bot.py` laufen lassen und den Dienst neu
  starten: `sudo systemctl restart telegram-anti-spam-bot`. Die Listen werden nur beim Start gelesen.
