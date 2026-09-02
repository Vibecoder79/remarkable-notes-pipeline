#!/bin/bash
# Wächter der reMarkable-Strecke: tote Links, liegengebliebene Dokumente, Stille.
# E-06.
#
# Aufruf im Crontab, BEWUSST OHNE `mit-sperre.sh` — liest nur Vault und
# Bibliothek und schickt höchstens eine Telegram-Nachricht:
#
#   heartbeat.sh remarkable-wachhund -- run-remarkable-wachhund.sh
#
# Warum es ihn gibt: Der Heartbeat sieht, DASS Abholer und Zuordner liefen —
# nicht, ob ein Link ins Leere zeigt, ein Dokument seit Tagen ohne Kürzel
# liegt oder lange nichts mehr ankam. Das hängt am Inhalt, nicht am Lauf.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo "ABBRUCH: python3 nicht im PATH." >&2; exit 127; }

"$HIER/remarkable_wachhund.py"
RC=$?

case "$RC" in
    0)  ;;
    77) echo "$(date -Iseconds) BEFUND gemeldet — siehe oben." >&2 ;;
    69) echo "$(date -Iseconds) VORUEBERGEHEND: naechster Lauf holt es nach." >&2 ;;
    *)  echo "$(date -Iseconds) FEHLSCHLAG: remarkable_wachhund.py endete mit $RC." >&2 ;;
esac
exit "$RC"
