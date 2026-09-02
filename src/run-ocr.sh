#!/bin/bash
# OCR-Nachlauf fuer gescannte PDFs. E-05 §7.
#
# Wird von Cron ueber heartbeat.sh aufgerufen — OHNE mit-sperre.sh aussen herum:
#   heartbeat.sh ocr -- run-ocr.sh
#
# Das ist der Unterschied zu allen anderen Jobs, und er ist Absicht. Dieser Job
# laeuft bis zu zwei Stunden. Haette er die Schreib-Sperre die ganze Zeit, wuerde
# die Abholung um 00:00 nach 15 Minuten Warten mit Fehlschlag abbrechen — jede
# Nacht. Deshalb: rechnen ohne Sperre, committen mit.
#
# Das ist zulaessig, weil die Rechenphase nur LIEST und in ein temporaeres
# Verzeichnis schreibt. Erst der Commit fasst das Repo an, und der dauert Sekunden.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Das Vault liegt nicht mehr neben diesem Skript: der Code wohnt seit 2026-08-06 in
# einem eigenen Repo (Notizen-Strecke), das Vault im privaten vault-Repo.
# Fester Ort mit Override, damit ein Test nicht den echten Bestand anfasst.
VAULT="${VAULT_DIR:-/opt/vault}"
BUDGET="${OCR_BUDGET:-7200}"

if [ ! -f "$VAULT/${VAULT_MARKER:-CLAUDE.md}" ] || [ ! -d "$VAULT/02 Projekte" ]; then
    echo "ABBRUCH: '$VAULT' ist keine Vault-Wurzel." >&2
    exit 1
fi

for W in pdftoppm tesseract pdfinfo; do
    command -v "$W" >/dev/null || {
        echo "ABBRUCH: '$W' fehlt. apt-get install tesseract-ocr tesseract-ocr-deu poppler-utils" >&2
        exit 127
    }
done

echo "=== OCR-Nachlauf $(date -Iseconds), Budget ${BUDGET}s ==="
python3 "$HIER/ocr_nachlauf.py" --budget "$BUDGET" "$@"
RC=$?

# --- Veroeffentlichen, jetzt mit Sperre ------------------------------------
cd "$VAULT" || exit 1

if [ -z "$(git status --porcelain -- '*— Volltext.md')" ]; then
    echo "  nichts erkannt, kein Commit"
    exit "$RC"
fi

"$HIER/mit-sperre.sh" -- bash -c '
    set -uo pipefail
    cd "$1" || exit 1
    n=$(git status --porcelain -- "*— Volltext.md" | wc -l)
    if ! git pull --ff-only origin main >/dev/null 2>&1; then
        echo "WARNUNG: pull --ff-only fehlgeschlagen — Arbeitskopie haengt zurueck." >&2
        exit 1
    fi
    git add -- "*— Volltext.md"
    if git commit -q -m "chore(vault): OCR-Nachlauf, ${n} Auszuege"; then
        if git push -q origin main 2>/dev/null; then
            echo "  veroeffentlicht: $(git rev-parse --short HEAD) (${n} Auszuege)"
        else
            echo "WARNUNG: Push fehlgeschlagen." >&2
            exit 1
        fi
    fi
' _ "$VAULT" || { [ "$RC" -eq 0 ] && RC=1; }

exit "$RC"
