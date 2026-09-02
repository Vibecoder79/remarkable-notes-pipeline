#!/bin/bash
# Lebenszeichen schreiben. E-04 §6.
#
# Zwei Aufrufarten:
#   heartbeat.sh <name>                    Erfolg von Hand melden
#   heartbeat.sh <name> -- <befehl...>     Befehl ausfuehren und Ergebnis melden
#
# Die zweite Form ist die richtige fuer Cron: sie meldet auch den FEHLSCHLAG.
# Ein Job, der nur bei Erfolg ein Lebenszeichen setzt, sieht im Bericht genauso
# aus wie einer, der gar nicht gestartet ist — der Unterschied zwischen
# "kaputt" und "vergessen" geht verloren.
#
# Zustand liegt bewusst NICHT im Vault-Repo: Zeitstempel sind Laufzeitdaten und
# haetten in der Versionsgeschichte nichts verloren. Sie wuerden bei jedem Lauf
# einen Commit erzeugen.
set -uo pipefail

# Zwei Konten schreiben dieselben Dateien — eigner und jobs, beide in der Gruppe
# `vault` ( Stufe 1). Die umask steht deshalb HIER fest, statt der PAM-
# Konfiguration ueberlassen zu bleiben: neue Dateien 0664, neue Verzeichnisse 0775,
# damit das jeweils andere Konto ueber die Gruppe weiterschreiben kann.
umask 002

# Ablage-Wurzel aus dem eigenen Ort ableiten statt hartkodieren. Dieses Skript liegt
# im Repo Notizen-Strecke (Umzug 2026-08-06). Die Ablage-Wurzel mit repo/,
# work/ und heartbeats/ liegt fest unter /var/lib/notizen-strecke.
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASIS="${VAULT_BASIS:-/var/lib/notizen-strecke}"
STATE_DIR="${HEARTBEAT_DIR:-${BASIS:-/var/lib/notizen-strecke}/heartbeats}"
NAME="${1:-}"

if [ -z "$NAME" ]; then
    echo "Aufruf: $0 <name> [-- <befehl...>]" >&2
    exit 64
fi
shift

mkdir -p "$STATE_DIR"

# --- Der Meldeweg (E-06 §5) -------------------------------------
# Der Telegram-Aufruf sitzt bewusst HIER und nicht im Statusbericht: er laeuft ueber
# ausgehendes HTTPS, nicht ueber Git, nicht ueber das Vault, nicht ueber den Sync.
# Damit ist der Zirkelschluss aus E-03 aufgeloest — ein Bericht ueber einen
# kaputten Kanal, der ueber denselben Kanal laeuft, ist keine Ueberwachung.
#
# Der Melder darf den Job NIE beeinflussen: sein Rueckgabewert wird verworfen, seine
# Zeitgrenze liegt bei 20 Sekunden. Ein Job soll nicht deshalb rot werden, weil
# Telegram gerade langsam ist.
# Ueberschreibbar, damit der Meldeweg pruefbar ist, ohne echte Nachrichten zu senden.
# Ein Melder, dessen Ausloesung man nicht testen kann, ist ein Melder auf Zusicherung.
MELDER="${MELDER:-$HIER/melder.sh}"

# Bremse gegen Alarm-Muedigkeit. `verdikt` laeuft alle fuenf Minuten; ein dauerhafter
# Fehler waere ohne diese Bremse 288 gleichlautende Nachrichten am Tag — genau das
# Flooding, gegen das E-06 §2 die Kanaltrennung setzt. Gemeldet wird deshalb der
# WECHSEL, und danach hoechstens einmal je MELDE_PAUSE_H.
MELDE_PAUSE_H="${MELDE_PAUSE_H:-6}"

melde() {
    if [ ! -x "$MELDER" ]; then
        echo "WARNUNG: '$MELDER' fehlt — diese Meldung geht nirgendwohin:" >&2
        echo "  $1" >&2
        return 0
    fi
    # Kein `wait`: die Meldung ist Nebenwirkung, nicht Bedingung. Ein haengender
    # Melder darf die Cron-Kette nicht aufhalten.
    #
    # Die Ausgabe wird NICHT verworfen. Hier stand `>/dev/null 2>&1`, und das war
    # derselbe Fehler in klein, gegen den dieser Kanal gebaut ist: Ein Melder, der
    # scheitert, haette geschwiegen — und ein Job-Ausfall waere unbemerkt geblieben,
    # WEIL die Meldung ueber ihn unbemerkt scheiterte. Aufgefallen am 2026-08-07 beim
    # ersten echten Lauf gegen Telegram: Der Job lief, die Meldung ging hinaus, und
    # nirgends stand, ob sie ankam.
    #
    # Jetzt landet das Ergebnis im Job-Log (`/var/log/notizen-strecke/<name>.log`, von Cron
    # umgeleitet) — inklusive der Fehlerklasse aus melder.sh.
    {
        "$MELDER" "$1"
        # Erst sichern, dann formatieren. `rc=$?` innerhalb einer Zeile mit
        # $(date …) liest den Rueckgabewert von `date`, nicht den des Melders —
        # die Kommandosubstitution laeuft zuerst. Beim Test genau so gemessen:
        # ein Fehlschlag mit 77 wurde als rc=0 protokolliert.
        local rc=$?
        local jetzt; jetzt=$(date -Iseconds)
        if [ "$rc" -eq 0 ]; then
            echo "$jetzt melder: zugestellt ($NAME)"
        else
            echo "$jetzt melder: NICHT zugestellt ($NAME, rc=$rc)" >&2
        fi
    } &
}

vorher_status() {
    [ -f "$STATE_DIR/$NAME" ] || { echo "keiner"; return; }
    grep -m1 '^status=' "$STATE_DIR/$NAME" | cut -d= -f2-
}

# Wann wurde zu diesem Job zuletzt gemeldet? Der Merker liegt neben den
# Lebenszeichen, also ausserhalb von Git — er ist Laufzeitzustand, kein Wissen.
pause_abgelaufen() {
    local merker="$STATE_DIR/.gemeldet-$NAME"
    [ -f "$merker" ] || return 0
    local letzte jetzt
    letzte=$(date -d "$(cat "$merker" 2>/dev/null)" +%s 2>/dev/null || echo 0)
    jetzt=$(date +%s)
    [ $(( (jetzt - letzte) / 3600 )) -ge "$MELDE_PAUSE_H" ]
}

merker_setzen() { date -Iseconds > "$STATE_DIR/.gemeldet-$NAME"; }

# --- Befund-Quittung: bekannt, terminiert, nicht vergessen -------------------
# Das Loch, das sie schliesst: Ein Befund kannte bis zum 2026-08-25 genau zwei
# Zustaende — neu (Alarm) und immer noch da (alle MELDE_PAUSE_H wieder Alarm). Es
# gab keinen Zustand «gesehen, terminiert». Damit erzeugte ein bekannter Befund
# dasselbe Signal wie ein frischer, und ab der zweiten Nachricht war es Rauschen.
# Gemessen am Cloud-Firewall-Befund: gefunden am 2026-08-22, danach rund zwoelf
# gleichlautende Nachrichten bis zum 2026-08-25. Die Messung hat funktioniert,
# gehandelt wurde drei Tage nicht — das ist E-06 §2 in klein.
#
# Was die Quittung NICHT tut, und das ist der ganze Punkt:
#
#   * Sie faelscht das Lebenszeichen nicht. `status=fehlschlag` bleibt stehen, der
#     Statusbericht zeigt den Job weiter rot. Unterdrueckt wird ausschliesslich der
#     TELEGRAM-Alarm — der Kanal, der abstumpft, nicht die Messung.
#   * Sie laeuft ab. Es gibt keine Quittung ohne Datum; nach dem Datum meldet der
#     Job wieder und sagt dazu, dass er ueberfaellig ist.
#   * Sie faellt bei Zweifel AUF. Ist die Datei unlesbar, das Datum unverstaendlich
#     oder leer, wird NICHT unterdrueckt. Eine kaputte Quittung, die einen Alarm
#     verschluckt, waere genau der stille Ausfall, gegen den diese ganze Strecke
#     gebaut ist: ungemessen darf nie wie in Ordnung aussehen.
QUITTUNG_DATEI="$STATE_DIR/.quittung-$NAME"

# Gibt das Verfallsdatum aus, wenn eine LESBARE Quittung vorliegt — sonst nichts.
quittung_bis() {
    [ -f "$QUITTUNG_DATEI" ] || return 1
    local bis
    bis=$(grep -m1 '^bis=' "$QUITTUNG_DATEI" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]')
    [ -n "$bis" ] || return 1
    # Ein Datum, das `date` nicht versteht, ist keine Quittung. Kein Rateversuch.
    date -d "$bis" +%Y%m%d >/dev/null 2>&1 || return 1
    printf '%s' "$bis"
}

# Vergleich als YYYYMMDD, nicht ueber Sekunden: `date -d 2026-09-05` ist Mitternacht,
# und ein Sekundenvergleich liesse die Quittung am letzten Tag schon abgelaufen sein.
# Sie gilt BIS EINSCHLIESSLICH dieses Tages.
quittung_gilt() {
    local bis="$1"
    [ "$(date -d "$bis" +%Y%m%d)" -ge "$(date +%Y%m%d)" ]
}

schreibe() {
    local status="$1" rc="$2" dauer="$3"
    printf 'zeit=%s\nstatus=%s\nrc=%s\ndauer_s=%s\nhost=%s\n' \
        "$(date -Iseconds)" "$status" "$rc" "$dauer" "$(hostname)" \
        > "$STATE_DIR/$NAME"
}

if [ "${1:-}" = "--" ]; then
    shift
    VORHER=$(vorher_status)
    START=$(date +%s)
    "$@"
    RC=$?
    ENDE=$(date +%s)
    if [ "$RC" -eq 0 ]; then
        schreibe erfolg "$RC" "$((ENDE - START))"
        # Erfolg meldet sich nicht — Stille bedeutet gesund (E-06 §2).
        # Die eine Ausnahme ist die ERHOLUNG: nach einem Fehlschlag ist Schweigen
        # zweideutig. Es kann heissen "wieder in Ordnung" oder "der Melder ist auch
        # noch gestorben". Eine Nachricht je Erholung ist kein Rauschen.
        if [ "$VORHER" = "fehlschlag" ]; then
            melde "OK  $NAME laeuft wieder ($(hostname), $((ENDE - START)) s)."
            rm -f "$STATE_DIR/.gemeldet-$NAME"
        fi
        # Eine Quittung gilt fuer EINEN Befund. Ist er weg, ist sie erledigt — sonst
        # deckt sie stillschweigend den naechsten, voellig anderen Fehlschlag mit ab.
        if [ -f "$QUITTUNG_DATEI" ]; then
            echo "$(date -Iseconds) quittung: $NAME laeuft wieder, Quittung entfernt"
            rm -f "$QUITTUNG_DATEI"
        fi
    else
        # Das Lebenszeichen wird IMMER geschrieben, auch mit Quittung. Der Bericht
        # muss den Befund weiter sehen; still wird nur der Alarmkanal.
        schreibe fehlschlag "$RC" "$((ENDE - START))"
        BIS=$(quittung_bis) || BIS=""
        if [ -n "$BIS" ] && quittung_gilt "$BIS"; then
            echo "$(date -Iseconds) quittung: Alarm zu $NAME unterdrueckt bis $BIS." \
                 "Der Befund steht weiter im Lebenszeichen (rc=$RC)."
        elif [ "$VORHER" != "fehlschlag" ] || pause_abgelaufen; then
            NACHSATZ=""
            [ -n "$BIS" ] && NACHSATZ="
Die Quittung ist am $BIS abgelaufen — dieser Befund ist UEBERFAELLIG."
            melde "FEHLSCHLAG  $NAME endete mit $RC nach $((ENDE - START)) s auf $(hostname).
Log: /var/log/notizen-strecke/$NAME.log$NACHSATZ"
            merker_setzen
        fi
    fi
    exit "$RC"
else
    schreibe erfolg 0 0
fi
