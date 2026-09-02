# 08 — Schwesterstrecken: Mail-Eingang und OCR

Zwei Programme, die nicht zum Tablet gehören, aber dieselbe Bauart teilen. Sie sind
hier, weil sie zeigen, wie sich das Muster überträgt.

---

## Der Mail-Eingang

[`notiz_abholer.py`](../src/notiz_abholer.py)

**Der Anwendungsfall in einem Satz:** Egal ob eigener Gedanke, Textauszug aus einem
Chat oder eine weitergeleitete Mail — soll etwas ins Vault, geht es per Mail an ein
zweites Dienstpostfach, immer mit `[KUERZEL] Thema` im Betreff.

Dasselbe Kürzel-Konzept, derselbe Gate-Gedanke, dieselbe Idempotenz. Zwei Unterschiede
sind lehrreich:

### Unterschied 1: Das Gate hat zwei Zweige

Beim Tablet kommt Post immer von aussen — ein DMARC-Gate genügt. Beim Mail-Eingang
schreibt auch der Eigner selbst, aus demselben Mandanten. Und:

> **Gemessen:** Exchange prüft **eigene Post nicht** (`dkim=none`, `dmarc=none`). Ein
> reines DMARC-Gate hätte das Hauptkonto des Eigners abgewiesen.

Deshalb zwei Zweige:

| Absender | Prüfung |
|---|---|
| **extern** | `dmarc=pass` **und** Alignment — wie beim Tablet |
| **intern** (eigene Domain) | Kopfzeile `X-MS-Exchange-Organization-AuthAs: Internal` |

Diese Kopfzeile setzt Exchange Online selbst und **entfernt sie an der
Organisationsgrenze von jeder Fremdpost**. Von aussen ist sie nicht mitzubringen —
gemessen: externe Absender trugen `Anonymous`.

Dazu vorgeschaltet eine **Allowlist** der erlaubten Absenderadressen. Ohne Liste kein
Gate, ohne Gate kein Lauf.

### Unterschied 2: Das Kürzel kommt NUR aus dem Betreff

Der Ersatzweg des Tablet-Zuordners («ersatzweise aus dem Rumpf») ist hier **bewusst
nicht übernommen.**

Der Rumpf ist hier eingefügter Fremdtext — ein weitergeleiteter Chat, eine fremde Mail.
Ein Kürzel darin wäre ein **Ziel aus Fremdinhalt**, und genau das schliesst
[E-04](entscheidungen/E-04%20Fremdinhalt%20ist%20Material,%20nie%20Auftrag.md) aus.

Beim Tablet ist der Rumpf ein selbst getippter Begleitsatz. Der Unterschied in der
Quelle rechtfertigt den Unterschied in der Regel.

### Links werden gespeichert, nicht geöffnet

Trägt der Betreff `Ressource:`, entsteht eine Zeiger-Notiz auf einen Link. **Der Link
wird nie aufgerufen.** Was dahinter steht, hat kein Job gelesen — und die Notiz sagt
das ausdrücklich.

Ein Job, der Links aus Fremdpost abruft, ist ein Job, den man von aussen auf beliebige
Adressen zeigen lassen kann.

---

## Der OCR-Nachlauf

[`ocr_nachlauf.py`](../src/ocr_nachlauf.py)

Für gescannte PDFs **im Vault** — nicht für die Handschrift vom Tablet.

### Warum ein Nachlauf und kein Durchlauf

```
pdftotext   Millisekunden
OCR         13 Sekunden pro Seite (200 dpi, eine vCPU)
```

Bei 70 solchen PDFs sind das mehrere Stunden. Ein Durchlauf würde entweder die Nacht
sprengen oder mittendrin abbrechen.

Deshalb: **ein Budget.** Der Job arbeitet ab, was in sein Zeitfenster passt, und macht
in der nächsten Nacht weiter. Ist nichts zu tun, endet er sofort.

### Der Fortschritt liegt im Ergebnis, nicht in einer Zustandsdatei

Ein angefangener Auszug trägt `ocr_seiten_fertig`, und der nächste Lauf hängt ab dieser
Seite an.

**Nur Fehlschläge brauchen ein Register** — sonst verbrennt ein kaputtes PDF jede Nacht
dieselben Minuten und blockiert den Fortschritt für alle anderen.

Der Unterschied ist grundsätzlich: Eine Zustandsdatei kann von der Wirklichkeit
abweichen. Ein Feld im Ergebnis kann das nicht.

### Die Sperre nur für den Commit

Das Programm committet **nicht**. Das macht der Wrapper — und hält die Sperre nur für
die paar Sekunden des Commits.

**Wer zwei Stunden lang sperrt, legt alle anderen Jobs lahm.**

### Grenze

Ausschliesslich Dokumente **im Vault**. Kein SharePoint, kein Cloud-Speicher, keine
Symlinks nach draussen.
