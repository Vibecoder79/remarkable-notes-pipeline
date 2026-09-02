# 09 — Nachbau: Schritt für Schritt

Für jemanden, der das nachbauen will. Reihenfolge zwingend; jeder Schritt endet mit
einer **Messung**, nicht mit einer Annahme.

Zeitbedarf realistisch: **ein Tag Arbeit, verteilt auf zwei** — weil eine Wartezeit von
mehreren Stunden dazwischenliegt (Schritt 4).

---

## Voraussetzungen

| | |
|---|---|
| Microsoft 365 | Administratorzugriff auf den Mandanten |
| Maschine | Linux, Python 3.11+, Zeitplaner. Eine kleine VM genügt |
| Pakete | `poppler-utils` (für `pdftotext`), `python3-fpdf`, für OCR `tesseract-ocr` |
| Quelle | Ein Gerät, das Dokumente per Mail versendet |
| Ziel | Ein Markdown-Verzeichnis mit der Struktur aus [02](02%20Das%20Vault%20—%20Struktur%20und%20Kuerzel.md) |

---

## Schritt 1 — Das Vault vorbereiten

**Das kommt zuerst.** Ohne Kürzel im Vault gibt es nichts, wogegen sich ein Name
auflösen liesse.

1. Die Baumstruktur anlegen (mindestens `02 Projekte`)
2. In mindestens einem Projekt-Hub `meeting_key: TEST` setzen
3. Prüfen:

```sh
VAULT_DIR=/pfad/zum/vault python3 src/kuerzel_register.py --register
```

**Messung:** Die Ausgabe listet `TEST` mit seinem Ordner. Ist sie leer, greift die
Strecke nirgends.

```sh
VAULT_DIR=/pfad/zum/vault python3 src/kuerzel_register.py --selbsttest
```

**Messung:** Sieben Fälle, alle wie erwartet — besonders die **Negativfälle**. Der
Zuordner muss anhalten, nicht raten.

## Schritt 2 — Dienstpostfach

Shared Mailbox anlegen, Unterordner `verarbeitet` und `abgewiesen` **auf Wurzel-Ebene**
neben dem Posteingang.

**Messung:** Eine Testmail vom Gerät kommt an.

## Schritt 3 — App registrieren, ohne Rechte

App anlegen, Application-ID notieren, **keine Berechtigungen**.

Wer hier schon `Mail.ReadWrite` erteilt, hat bis Schritt 5 eine App mit
mandantenweitem Postfachzugriff.

## Schritt 4 — Access Policy, dann warten

Sicherheitsgruppe und Policy nach
[03, Schritt 3](03%20Microsoft%20365%20—%20die%20Einrichtung.md#schritt-3--sicherheitsgruppe-und-access-policy).

**Messung:** `Test-ApplicationAccessPolicy` in **beide** Richtungen.

> **Jetzt kommt die Wartezeit.** Die Durchsetzung braucht Stunden — gemessen rund fünf.
> In dieser Zeit blockt die Policy auch das erlaubte Postfach. **Das ist normal. Nicht
> schrauben.** Wer jetzt umbaut, verschlimmert.

## Schritt 5 — Rechte erteilen

`Mail.ReadWrite` und `Mail.Send` als **Anwendungsberechtigung**, mit
Administratorzustimmung. Client-Secret erzeugen (Spalte «Wert»).

Zweite App für die Bibliothek mit `Sites.Selected`.

**Messung, per Graph und nicht per Cmdlet:**

```
Postfach-App    → Dienstpostfach          200
Postfach-App    → anderes Postfach        403
Bibliotheks-App → Dienstpostfach          403
```

Alle drei müssen stimmen. Zwei von drei heisst: die Trennung steht nicht.

## Schritt 6 — SharePoint

Site anlegen (oder eine bestehende nehmen), Grant über
`POST /sites/{id}/permissions` setzen.

Bibliothek `remarkable` **von Hand**: fünf Spalten, drei Ansichten
([03, Schritt 7](03%20Microsoft%20365%20—%20die%20Einrichtung.md#schritt-7--bibliothek-und-spalten-von-hand)).
Von Hand, weil `Sites.Selected` keine Schema-Änderungen erlaubt.

**Messung — Schreibprobe:** Testdatei hochladen, **alle fünf Spalten setzen**, lesen,
löschen. Erst wenn die Spalten schreibbar sind, trägt die Bibliothek.

## Schritt 7 — Geheimnisse ablegen

```sh
sudo install -d -m 0750 -o jobs -g jobs /etc/notizen-strecke
cp einrichtung/m365.env.beispiel     /etc/notizen-strecke/m365.env
cp einrichtung/postfach.env.beispiel /etc/notizen-strecke/postfach.env
sudo chmod 0640 /etc/notizen-strecke/*.env
```

Werte eintragen, **Rotationsdatum als Kommentar**. Es gibt keine Erinnerung, die von
selbst kommt.

## Schritt 8 — Abnahme der Programme

```sh
export VAULT_DIR=/pfad/zum/vault SECRETS_DIR=/etc/notizen-strecke

python3 src/remarkable_abholer.py --pruefe-zugang   # Postfach + Bibliothek
python3 src/remarkable_abholer.py --trockenlauf     # was würde passieren
python3 src/remarkable_zuordner.py --pruefe-zugang
python3 src/remarkable_zuordner.py --trockenlauf
```

**Messung:** Der Trockenlauf des Abholers zeigt `[TROCKEN] würde hochladen: …`. Der des
Zuordners zeigt je Dokument, ob eine Textebene da ist.

Dann die Testproben — sie brauchen **keinen** Microsoft-Zugang:

```sh
for t in tests/*.py; do python3 "$t" || echo "FEHLGESCHLAGEN: $t"; done
```

**Messung:** Fünfmal «GRÜN».

## Schritt 9 — Erster echter Lauf

Ein Dokument vom Gerät mit `[TEST] Erster Versuch` senden. Dann:

```sh
python3 src/remarkable_abholer.py
python3 src/remarkable_zuordner.py
```

**Messung, in dieser Reihenfolge:**

1. Das PDF liegt in der Bibliothek, `Status = Neu`, `Eingang` gesetzt
2. Nach dem Zuordner: `Status = Verarbeitet`, `Projekt = TEST`
3. Im Vault liegt `Notizen/…[TEST] Erster Versuch.md`
4. Die Notiz trägt `artefakt:` mit einer aufrufbaren URL

Fehlt Nummer 3, aber Nummer 1 stimmt, ist das Kürzel nicht im Register — Schritt 1
wiederholen.

## Schritt 10 — Gegenprobe: das Gate

Eine Mail **von einer anderen Adresse** an das Dienstpostfach senden.

**Messung:** Sie landet in `abgewiesen`, mit Grund im Log. Wandert sie in die
Bibliothek, ist das Gate offen — dann aufhören und Schritt 4 prüfen.

Diese Gegenprobe ist wichtiger als alle vorherigen: **Ein Gate, das stillschweigend
durchlässt, fällt im Betrieb nicht auf.** Eine Mail von einem Angreifer sieht aus wie
eine vom Gerät.

## Schritt 11 — Zeitplaner

Erst jetzt. Vorlage: [`einrichtung/cron.beispiel`](../einrichtung/cron.beispiel)

**Messung:** Nach einer Stunde stehen Läufe im Log, und das Lebenszeichen ist frisch.

## Schritt 12 — Rückweg (optional)

Zweite Bibliothek, Verknüpfung zum Cloud-Speicher, dann:

```sh
python3 src/remarkable_index.py --schreibprobe
python3 src/remarkable_index.py
```

**Messung am Gerät:** Integration öffnen, «Meine Dateien» → Bibliothek → Index
importieren. Erscheint die Bibliothek nicht, fehlt die OneDrive-Verknüpfung — sie ist
**Pflicht**, nicht Bequemlichkeit.

---

## Was du danach hast

- Ein Dokument vom Gerät ist nach spätestens 30 Minuten im richtigen Projekt
- Ein Dokument ohne Kürzel liegt sichtbar in «Ohne Zuordnung» und wartet
- Eine abgewiesene Mail ist gezählt, nicht verschwunden
- Der Wächter meldet tote Links, Liegengebliebenes und Stille — sonst schweigt er

## Was du **nicht** hast

- Handschrifterkennung
- Automatischen Rückweg aufs Gerät
- Eine Zuordnung für Dokumente ohne Kürzel
