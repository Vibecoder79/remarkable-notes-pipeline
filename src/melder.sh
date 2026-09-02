#!/bin/bash
# Der administrative Meldeweg — Telegram. E-06.
#
# Warum es diesen Weg gibt
# ------------------------
# Der Statusbericht liegt im Vault. Wer die Seite nicht oeffnet, sieht auch ein rotes
# Feld nicht — und genau so sind zwischen dem 2026-06-13 und dem 2026-07-29 vier
# Cloud-Routinen sechs Wochen lang tot gewesen. Ein Bericht ist eine Bringschuld des
# Lesers; dieser Kanal ist eine Holschuld des Systems.
#
# Warum ausgerechnet Telegram und warum ausgehend
# -----------------------------------------------
# Der VPS hat keinen offenen Port (E-13). Alles laeuft ausgehend: senden per POST,
# und falls jemals Antworten gebraucht werden, per `getUpdates` im Long Polling —
# NIEMALS per Webhook. Das Muster der Trading Platform (Webhook) traegt hier nicht.
#
# Warum der Melder nicht an dem haengt, was er ueberwacht (E-06 §5)
# --------------------------------------------------------------------
# Kein Git, kein Vault, kein Sync — nur ausgehendes HTTPS. Ein Bericht ueber einen
# kaputten Kanal, der ueber denselben Kanal laeuft, ist keine Ueberwachung. Deshalb
# liest dieses Skript das Vault nicht einmal an.
#
# Stille bedeutet gesund (E-06 §2)
# -----------------------------------
# Dieses Skript wird NICHT nach jedem erfolgreichen Lauf aufgerufen. Zehn Jobs mal
# taeglich waeren ueber 300 Nachrichten im Monat, die alle dasselbe sagen; nach zwei
# Wochen schaut niemand mehr hin, und der Kanal ist so tot wie die Statusseite.
# Gesendet wird bei Fehlschlag, bei Ueberfaelligkeit — und einmal taeglich die Zeile,
# die beweist, dass der Melder selbst noch lebt.
#
# Titel gehen nicht nach Telegram (E-06 §3)
# --------------------------------------------
# Dieses Skript sendet, was ihm uebergeben wird; die Regel gilt beim Aufrufer. Wer
# Vault-Inhalte meldet, prueft vorher `classification` — fehlt das Feld, gilt die
# Notiz als vertraulich, und es geht nur die Zahl hinaus, nie der Titel. Job-Namen
# und Rueckgabewerte sind davon nicht betroffen: sie sind Betriebsdaten, kein Inhalt.
#
# Aufruf
# ------
#   melder.sh <text...>        Meldung senden
#   melder.sh -                Meldung von stdin lesen
#   melder.sh --selbsttest     Token und Chat beweisen: getMe + eine Testnachricht
#   melder.sh --chat-id        Long Polling einmal ausfuehren, gefundene Chats zeigen
#
# Rueckgabewerte — die Klassen aus E-03 §5, damit der Aufrufer sie unterscheiden kann
#   0   gesendet UND von Telegram bestaetigt
#   64  Aufruffehler
#   69  voruebergehend: nicht erreichbar, Zeitueberschreitung, 5xx, Rate-Limit
#   77  dauerhaft: Token falsch, Bot blockiert, Chat unbekannt — erneut hilft nie
#   78  Konfiguration fehlt
set -uo pipefail

# SECRETS_DIR gilt auch hier — dieselbe Konvention wie `geheimnis()` in
# freigabe_gemeinsam.py. Ohne sie meldete jede Probe, die ihre Geheimnisse auf
# einen leeren Ordner umbiegt, trotzdem in den ECHTEN Kanal: Am 2026-08-12 standen
# so vier Test-Szenarien aus stufe3_probe (`…-r2`, Verdikt `vielleicht`) als
# vermeintliche Betriebsfehler im Telegram-Kanal des Operators.
KONFIG="${TELEGRAM_ENV:-${SECRETS_DIR:-/etc/notizen-strecke}/telegram.env}"
ZEITGRENZE="${TELEGRAM_TIMEOUT:-20}"
# Telegram nimmt 4096 Zeichen je Nachricht. Laengeres wird SICHTBAR gekappt —
# stilles Abschneiden waere dieselbe Klasse Fehler wie ein stiller Fallback.
MAXLAENGE=4000

meldung_ausgeben() { echo "melder: $*" >&2; }

# --- Konfiguration ---------------------------------------------------------
# Nicht `source`, sondern zeilenweise lesen: die Datei ist eine Wertetabelle, kein
# Programm. Ein `source` wuerde beliebigen Shell-Code ausfuehren, den jemand dort
# ablegt — bei einer Datei, die per Definition Geheimnisse traegt, ist das die
# falsche Voreinstellung.
lies_konfig() {
    if [ ! -r "$KONFIG" ]; then
        meldung_ausgeben "ABBRUCH: Konfiguration '$KONFIG' fehlt oder ist nicht lesbar."
        meldung_ausgeben "         Erwartet werden die Zeilen TELEGRAM_BOT_TOKEN=... und TELEGRAM_CHAT_ID=..."
        meldung_ausgeben "         Rechte: chmod 600, Eigner der Job-Nutzer. Nie ins Repo (Secrets-Policy)."
        return 78
    fi
    TOKEN=$(grep -m1 '^TELEGRAM_BOT_TOKEN=' "$KONFIG" | cut -d= -f2- | tr -d '"'"'"' \r')
    CHAT=$(grep -m1 '^TELEGRAM_CHAT_ID=' "$KONFIG" | cut -d= -f2- | tr -d '"'"'"' \r')
    if [ -z "${TOKEN:-}" ] || [ -z "${CHAT:-}" ]; then
        meldung_ausgeben "ABBRUCH: TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID fehlt in '$KONFIG'."
        return 78
    fi
    return 0
}

# --- Ein Aufruf gegen die Bot-API ------------------------------------------
# Der Rueckgabewert von curl beweist NICHTS ueber das Ergebnis: curl meldet 0, sobald
# eine HTTP-Antwort kam — auch bei 401. Deshalb wird die Antwort selbst geprueft.
# Dieselbe Lehre wie bei `claude -p`, das mit rc=0 endet und "Unknown command" ausgibt.
#
# Die URL enthaelt das Token. Sie wird deshalb NIE ausgegeben, auch nicht im Fehlerfall.
api() {
    local methode="$1"; shift
    local antwort http
    antwort=$(curl -sS --max-time "$ZEITGRENZE" \
                   -w '\n%{http_code}' \
                   "https://api.telegram.org/bot${TOKEN}/${methode}" \
                   "$@" 2>/dev/null)
    local curl_rc=$?
    if [ "$curl_rc" -ne 0 ]; then
        # Netzwerkebene: nichts angekommen. Voruebergehend, bis das Gegenteil feststeht.
        meldung_ausgeben "Telegram nicht erreichbar (curl endete mit $curl_rc) — voruebergehend."
        return 69
    fi
    http="${antwort##*$'\n'}"
    ANTWORT="${antwort%$'\n'*}"

    case "$http" in
        200)
            # Auch 200 ist kein Beweis. Telegram antwortet mit {"ok":true,...}.
            if printf '%s' "$ANTWORT" | grep -q '"ok":[[:space:]]*true'; then
                return 0
            fi
            meldung_ausgeben "Telegram antwortete mit HTTP 200, aber ok!=true: $(kurz "$ANTWORT")"
            return 77
            ;;
        429|5??)
            meldung_ausgeben "Telegram HTTP $http — voruebergehend, naechster Lauf holt es nach."
            return 69
            ;;
        *)
            meldung_ausgeben "Telegram HTTP $http — dauerhaft: $(kurz "$ANTWORT")"
            meldung_ausgeben "  401 = Token falsch · 403 = Bot blockiert oder Chat nie gestartet · 400 = Chat-ID falsch"
            return 77
            ;;
    esac
}

kurz() { printf '%.300s' "$1"; }

senden() {
    local text="$1"
    if [ "${#text}" -gt "$MAXLAENGE" ]; then
        text="${text:0:$MAXLAENGE}"$'\n\n[gekuerzt — vollstaendig im Job-Log auf dem Host]'
    fi
    # Kein parse_mode: der Text geht als Klartext hinaus. Markdown waere ein
    # Fussangel-Format — ein Unterstrich in einem Dateinamen laesst Telegram die
    # ganze Nachricht mit 400 ablehnen, und dann faellt die Meldung aus, die
    # gerade das Problem melden sollte.
    api sendMessage \
        --data-urlencode "chat_id=${CHAT}" \
        --data-urlencode "text=${text}" \
        --data-urlencode "disable_web_page_preview=true"
}

# --- Unterbefehle ----------------------------------------------------------
case "${1:-}" in
    --selbsttest)
        lies_konfig || exit $?
        # `if ! api getMe; then exit $?; fi` waere hier falsch: nach der Negation ist
        # $? der NEGIERTE Wert, ein Fehlschlag endete also mit 0. Beim ersten Test
        # dieses Skripts gemessen — der Selbsttest meldete Erfolg auf ein HTTP 401.
        # Dieselbe Klasse Fehler, gegen die dieser ganze Kanal gebaut wird.
        api getMe; RC=$?
        [ "$RC" -eq 0 ] || exit "$RC"
        name=$(printf '%s' "$ANTWORT" | grep -o '"username":"[^"]*"' | head -1 | cut -d'"' -f4)
        echo "getMe: Bot '@${name:-unbekannt}' antwortet."
        senden "Melder: Selbsttest $(date -Iseconds) auf $(hostname). Diese Nachricht beweist Token und Chat-ID."
        RC=$?
        if [ "$RC" -eq 0 ]; then
            echo "sendMessage: von Telegram bestaetigt (ok=true)."
            echo "Der Kanal traegt. Ab jetzt gilt: Stille bedeutet gesund."
        fi
        exit "$RC"
        ;;
    --chat-id)
        # Long Polling, nicht Webhook — E-06 §1. Ein einzelner Abruf genuegt, um
        # die Chat-ID zu finden: der Operator schreibt dem Bot einmal irgendetwas.
        lies_konfig >/dev/null 2>&1 || {
            TOKEN=$(grep -m1 '^TELEGRAM_BOT_TOKEN=' "$KONFIG" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' \r')
            [ -z "${TOKEN:-}" ] && { meldung_ausgeben "ABBRUCH: TELEGRAM_BOT_TOKEN fehlt in '$KONFIG'."; exit 78; }
        }
        api getUpdates --data-urlencode "timeout=10" --data-urlencode "limit=20"; RC=$?
        [ "$RC" -eq 0 ] || exit "$RC"
        echo "Gefundene Chats (Long Polling, getUpdates):"
        printf '%s' "$ANTWORT" | grep -o '"chat":{"id":-\?[0-9]*[^}]*' \
            | sed 's/.*"id":\(-\?[0-9]*\).*/  Chat-ID: \1/' | sort -u
        echo
        echo "Leer? Dann hat dem Bot noch niemand geschrieben. Einmal /start an ihn senden."
        exit 0
        ;;
    "")
        meldung_ausgeben "Aufruf: $0 <text...> | - | --selbsttest | --chat-id"
        exit 64
        ;;
    -)
        TEXT=$(cat)
        ;;
    *)
        TEXT="$*"
        ;;
esac

[ -n "${TEXT:-}" ] || { meldung_ausgeben "ABBRUCH: leerer Text, nichts zu melden."; exit 64; }

lies_konfig || exit $?
senden "$TEXT"
exit $?
