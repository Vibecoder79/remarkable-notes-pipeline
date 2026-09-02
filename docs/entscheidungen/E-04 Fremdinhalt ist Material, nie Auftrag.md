# E-04 — Fremdinhalt ist Material, nie Auftrag

**Status:** entschieden · **Betrifft:** Zuordner, Sprachnotiz-Zweig, Mail-Eingang

## Die Frage

In der Zeiger-Notiz landet Text, den nicht der Eigner geschrieben hat: der Mailrumpf,
die Textebene des PDFs, ein Transkript. Spaeter liest ein Sprachmodell diesen Text.
Was, wenn darin eine Anweisung steht?

## Die Entscheidung

**Alles, was nicht vom Eigner stammt, ist Datenmaterial.** Steht darin etwas, das wie
eine Anweisung klingt, wird es **zitiert und gemeldet, nie befolgt** — auch dann
nicht, wenn es plausibel, dringend oder ausdruecklich an die Maschine adressiert wirkt.

Mechanisch umgesetzt an drei Stellen:

1. **Im Vault sichtbar gerahmt.** Mailrumpf und Textebene stehen in der Notiz als
   Zitatblock, nicht als Fliesstext. Wer die Notiz liest, sieht die Grenze.
2. **Im Frontmatter etikettiert.** `provenance.origin: ingested-external`.
3. **Vor jedem Modellaufruf eingezaeunt.** `fremd_zaun.py` setzt Marken um den
   Fremdtext, mit dem ausdruecklichen Satz, dass alles darin Material ist.

## Die ehrliche Grenze

**Der Zaun senkt die Erfolgsrate eines Angriffs, garantiert aber nichts.** Wer sich
darauf verlaesst, hat eine Absicherung mit Anschein.

Deshalb traegt die Architektur die Last, nicht die Erkennung: Der Sprachnotiz-Zweig
gibt dem Modell **keinen Schreibort** und **keinen Pfad** zurueckzugeben, sondern eine
Nummer in eine maschinell gebaute Liste ([E-07](E-07%20Verknuepfen%20und%20melden%20statt%20fragen.md)).
Ein getaeuschtes Modell kann dann hoechstens die falsche von zwei Notizen waehlen —
eine Zeile, in fuenf Sekunden geloescht.

## Fehlendes Etikett heisst «unbekannt»

Traegt eine Datei keine Herkunftsangabe, gilt sie als **Fremdinhalt**, nicht als
vertrauenswuerdig. Ein fehlendes Etikett blockiert nie einen Lauf — es stuft herab.
