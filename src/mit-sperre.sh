#!/bin/bash
# Nur ein Job fasst das Vault gleichzeitig an, und was er schreibt, committet er.
# Die Vault-Sperre.
#
# Aufruf:  mit-sperre.sh -- <befehl...>
#
# Gedacht INNERHALB von heartbeat.sh, nicht darum herum:
#   heartbeat.sh abholung -- mit-sperre.sh -- run-abholung.sh
#
# So wird ein Sperr-Timeout als Fehlschlag im Statusbericht sichtbar. Andersherum
# wuerde der Heartbeat gar nicht erst geschrieben, und ein blockierter Job saehe
# aus wie ein Job, der nie gestartet ist.
#
# Die Nachernte
# ------------------------
# Nach dem Lauf committet dieses Skript, was der Lauf im Vault geschrieben hat.
#
# Warum HIER und nicht in den Jobs: Am 2026-08-30 gemessen — 23 Jobs schreiben ins
# Vault, 9 committeten, 13 nicht. Der Rueckstand war der kleinere Schaden. Der
# groessere: Die Ausgabe der 13 wanderte in SESSION-Commits mit fachlicher
# Nachricht. `der Transkript-Dienst-Kontext.md` steckt in «feat(vbs): vom Wert zum Preis»,
# `Agenten-Register.md` in «feat(agenten): Sub-Agents vervollstaendigt». Damit
# gilt die Auflage aus E-02 nicht mehr: ein Commit gehoert einem Lauf, «damit
# ist git revert ein Befehl und keine Suche».
#
# Dreizehn Skripte einzeln nachzuruesten waere dreizehn Stellen fuer ein Verhalten,
# das ueberall gleich sein muss. Dieses Skript ist die Klammer um alle 23: Es
# kennt den Job-Namen, es weiss wann der Lauf beginnt, und es haelt die Sperre,
# waehrend er laeuft.
#
# **Nur die eigene Ausgabe.** Der Vergleich laeuft ueber die Aenderungszeit gegen
# eine Marke, die vor dem Lauf gesetzt wird. Ein pauschales `git add -A`
# ist hier ausgeschlossen, und zwar nicht aus Vorsicht: Am 2026-08-21 zog der
# Freigabe-Job zweimal halbfertige Session-Arbeit in seinen Commit. Der Fehler
# waere sonst nur umgedreht.
#
# Ein Job, der selbst committet, laesst nichts offen — die Nachernte findet dann
# nichts und schweigt. Deshalb braucht keiner der 9 eine Aenderung.
#
# Abschaltbar mit VAULT_NACHERNTE=nein, gedacht fuer Trockenlaeufe und fuer den
# Fall, dass ein Job absichtlich Halbfertiges liegen laesst.
#
# Warum flock und keine selbstgebaute Sperrdatei: der Kernel gibt die Sperre frei,
# sobald der haltende Prozess endet — auch bei kill -9 und bei Stromausfall. Eine
# Datei, die ein abgestuerzter Job hinterlaesst, legt sonst alle anderen Jobs still,
# bis jemand von Hand aufraeumt. Genau der Fehler, der Ueberwachung unbrauchbar
# macht: eine Sicherung, die haeufiger selbst ausfaellt als das, was sie sichert.
set -uo pipefail

SPERRDATEI="${VAULT_LOCK:-/var/lock/vault-schreiben.lock}"
# Wartezeit: lang genug fuer einen vollstaendigen Lint-Lauf, kurz genug, dass ein
# haengender Job nicht stundenlang unbemerkt blockiert.
WARTE_S="${VAULT_LOCK_WARTE:-900}"
VAULT_DIR="${VAULT_DIR:-/opt/vault}"
NACHERNTE="${VAULT_NACHERNTE:-ja}"

# --- Die Nachernte ---------------------------------------------------------

nachernte() {
    local marke="$1" job="$2" rc="$3"
    cd "$VAULT_DIR" || { echo "Nachernte: '$VAULT_DIR' nicht erreichbar." >&2; return 0; }

    # Der Dateiname steht ab Spalte 4, davor die Statusspalten (`M `, `??`).
    # `awk '{print $1}'` haette hier die STATUSSPALTE gelesen — der Fehler, der am
    # 2026-08-28 sieben statt einer Datei committete.
    #
    # `-z`, weil Vault-Pfade Leerzeichen und Umlaute tragen.
    # `--untracked-files=all`, weil Git ein neues VERZEICHNIS sonst zu einem
    # einzigen Eintrag zusammenfasst und die Dateien darin nie sichtbar werden.
    local OFFEN=() NEU=() FREMD=0 f
    mapfile -d '' -t OFFEN < <(git status --porcelain -z --untracked-files=all \
                               | while IFS= read -r -d '' e; do printf '%s\0' "${e:3}"; done)

    # Die eine Frage: Hat DIESER Lauf die Datei geschrieben? Nicht: war sie vorher
    # sauber. In einer Arbeitskopie, in die Sitzungen und Jobs gleichzeitig
    # schreiben, ist das der ganze Unterschied.
    for f in "${OFFEN[@]}"; do
        [ -f "$f" ] || continue          # Loeschungen faengt die Zeitmarke nicht
        [ "$f" -nt "$marke" ] && NEU+=("$f")
    done
    FREMD=$(( ${#OFFEN[@]} - ${#NEU[@]} ))

    if [ "${#NEU[@]}" -eq 0 ]; then
        [ "$FREMD" -gt 0 ] && echo "Nachernte: nichts vom Lauf, ${FREMD} fremde(r) Pfad(e) unberuehrt."
        return 0
    fi
    [ "$FREMD" -gt 0 ] && echo "Nachernte: ${FREMD} fremde(r) offene(r) Pfad(e) bewusst nicht mitcommittet."

    if ! git pull --ff-only origin main >/dev/null 2>&1; then
        echo "Nachernte: pull --ff-only fehlgeschlagen, nicht committet — Arbeitskopie haengt zurueck." >&2
        return 0
    fi

    # Ein Fehlschlag des Jobs macht das Geschriebene nicht ungeschrieben. Es bleibt
    # liegen, wenn wir es nicht nehmen — und es gehoert trotzdem diesem Lauf. Der
    # Zustand wird benannt statt verschwiegen.
    local zusatz=""
    [ "$rc" -ne 0 ] && zusatz=", Lauf endete mit $rc"

    git add -- "${NEU[@]}"
    # `-- "${NEU[@]}"` auch beim commit: `git add` allein genuegt nicht. Ohne die
    # Pfadangabe nimmt `git commit` mit, was eine Sitzung vorher gestaget hat.
    if git commit -q -m "chore(${job%%.*}): ${#NEU[@]} Datei(en) aus dem Lauf vom $(date +%F)${zusatz}" \
                  -- "${NEU[@]}"; then
        git push -q origin main 2>/dev/null \
            && echo "Nachernte: ${#NEU[@]} Datei(en) committet und gepusht." \
            || echo "Nachernte: ${#NEU[@]} Datei(en) committet, push fehlgeschlagen."
    else
        echo "Nachernte: commit fehlgeschlagen." >&2
    fi
    return 0
}


if [ "${1:-}" != "--" ]; then
    echo "Aufruf: $0 -- <befehl...>" >&2
    exit 64
fi
shift

if [ "$#" -eq 0 ]; then
    echo "Kein Befehl angegeben." >&2
    exit 64
fi

# 9<> statt 9>: ">" wuerde die Datei beim Oeffnen leeren — also BEVOR flock greift.
# Ein wartender Job loescht damit den Eintrag genau des Jobs, auf den er wartet,
# und die Fehlermeldung unten meldet "unbekannt". Gemessen und behoben 2026-07-30.
exec 9<>"$SPERRDATEI" || { echo "Sperrdatei '$SPERRDATEI' nicht anlegbar." >&2; exit 73; }

START=$(date +%s)
if ! flock -w "$WARTE_S" 9; then
    echo "ABBRUCH: Sperre nach ${WARTE_S}s nicht bekommen — ein anderer Job schreibt." >&2
    echo "         Haltender Prozess laut Sperrdatei: $(cat "$SPERRDATEI" 2>/dev/null || echo unbekannt)" >&2
    exit 75   # EX_TEMPFAIL: nicht kaputt, nur gerade nicht dran
fi
GEWARTET=$(( $(date +%s) - START ))

# Wer haelt gerade? Rein informativ fuer den Fehlerfall oben — die Sperre selbst
# haengt am Dateideskriptor, nicht am Inhalt. Erst jetzt leeren und schreiben:
# vor dem flock waere es ein Eingriff in fremden Zustand.
: > "$SPERRDATEI"
printf 'pid=%s\njob=%s\nseit=%s\n' "$$" "${1##*/}" "$(date -Iseconds)" > "$SPERRDATEI"

[ "$GEWARTET" -gt 0 ] && echo "Sperre nach ${GEWARTET}s bekommen."

# --- Die Sperre bekanntgeben -------------------------------------
# Ohne diese Zeile kann NICHTS, was hier drin laeuft, seine eigene Sperre von einer
# fremden unterscheiden. Es gibt kein Signal dafuer: `flock -n` meldet nur "belegt",
# und in der Prozessliste steht der eigene Elternprozess genauso da wie ein
# konkurrierender Job.
#
# Am 2026-08-20 hat der naechtliche Lint-Lauf genau daran nichts getan und trotzdem
# Erfolg gemeldet. Die Kette ist
#
#     heartbeat.sh lint -- mit-sperre.sh -- run-lint.sh -> claude -p /lint
#
# also haelt DIESES Skript die Sperre, waehrend der Lint-Lauf darin laeuft. Das
# Modell hat sie geprobt, belegt gefunden, den Prozess `claude -p /lint` gesehen —
# sich selbst — und vor dem ersten Schreibvorgang gestoppt, in der Annahme, "der
# Nachtlauf" hole das nach. Es WAR der Nachtlauf. Kein Report, keine
# Kennzahlen-Zeile, kein Index; der Kontrolllauf dazu hing an dieser Zeile.
#
# Das Modell hat dabei sauber gemessen und richtig geschlossen. Der Fehler lag
# darin, dass die Frage "ist das meine Sperre?" gar nicht beantwortbar war.
#
# Weitergegeben wird die PID dieses Skripts, nicht bloss eine 1: So laesst sich im
# Zweifel gegen die Sperrdatei pruefen, ob es WIRKLICH dieselbe Sperre ist und
# nicht eine geerbte Variable aus einem laengst beendeten Lauf.
export VAULT_SPERRE_PID="$$"
export VAULT_SPERRE_DATEI="$SPERRDATEI"

# Die Marke fuer die Nachernte, eine Sekunde zurueck: Wer sie auf JETZT setzt,
# verliert Dateien, die im selben Sekundenbruchteil entstehen.
MARKE=""
if [ "$NACHERNTE" = "ja" ] && [ -d "$VAULT_DIR/.git" ]; then
    MARKE=$(mktemp) && touch -d "1 second ago" "$MARKE"
fi

"$@"
RC=$?

# --- Nachernte: committen, was DIESER Lauf geschrieben hat --------
if [ -n "$MARKE" ]; then
    nachernte "$MARKE" "${1##*/}" "$RC"
    rm -f "$MARKE"
fi

# Inhalt leeren, damit die Datei nicht den letzten Halter vortaeuscht. Die Sperre
# selbst faellt mit dem Prozessende — auch bei kill -9, dafuer sorgt der Kernel.
: > "$SPERRDATEI"
exit "$RC"
