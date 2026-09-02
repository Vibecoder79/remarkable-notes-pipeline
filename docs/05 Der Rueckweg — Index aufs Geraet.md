# 05 — Der Rückweg: Kürzel-Index aufs Gerät

[`remarkable_index.py`](../src/remarkable_index.py) · nächtlich

## Warum es ihn gibt

Die Strecke hat genau eine echte Schwachstelle: **den Tippfehler beim Kürzel.** Wer
`[ACEM]` statt `[ACME]` schreibt, landet in «Ohne Zuordnung» — kein Datenverlust, aber
Handarbeit.

Dagegen hilft kein Code, sondern ein Nachschlagezettel **auf dem Gerät**.

## Der Weg

```
Job ──Sites.Selected──► Bibliothek 'an-remarkable'
                                │
                                │ OneDrive-Verknüpfung (einmalig, von Hand)
                                ▼
                      «Meine Dateien» des Eigners
                                │ Tablet-Integration, Anmeldung am Gerät
                                ▼
                      Tablet: browse + tap (manueller Import)
```

**Kein neues Recht, kein neues Geheimnis.** Der Job schreibt mit dem bestehenden
Site-Grant; die Verbindung Tablet ↔ Microsoft läuft über das persönliche Konto des
Eigners.

## Was im PDF steht

1. Oben die **Namensregel** — `[KUERZEL] Thema` und `[KUERZEL] NOTIZ Thema`
2. Darunter alle Kürzel, gruppiert nach Baum, je Gruppe alphabetisch

Das Register kommt aus `kuerzel_register.lade_register()` — **derselben Quelle**, gegen
die der Zuordner auflöst. Der Index zeigt exakt das, was die Strecke versteht. Eine
zweite Kürzelliste gäbe es sonst doch.

## Drei Auslegungsentscheidungen

**Stabiler Dateiname, jeder Lauf überschreibt.** Am Gerät ist es immer dieselbe,
aktuelle Datei — statt einer wachsenden Sammlung datierter Fassungen.

**Nach dem Upload wird die Grösse zurückgelesen.** Erst der Nachweis macht den Upload
zum Ergebnis. Ein HTTP 200 ist eine Zusage, keine Messung.

**Ein leeres Register lädt nie hoch** (dauerhafter Fehler). Ein leerer Index wäre eine
Antwort, die wie eine Antwort aussieht und keine ist.

## Fehlerbild, bewusst anders als beim Abholer

| Lage | hier | beim Abholer |
|---|---|---|
| Bibliothek fehlt | **vorübergehend** — die Anlage von Hand ist der geplante Weg, der nächste Lauf heilt | **dauerhaft** — Konfigurationsbruch |

## Werkzeugwahl: fpdf2

Die kleinste Abhängigkeit, die **Unicode-Schriften einbetten** kann. Die Ordnernamen
tragen Umlaute, und der eingebaute Latin-1-Zeichensatz von PDF reicht dafür nicht.

Ein Office-Renderer oder ein Browser-Renderer wäre auf einer kleinen Maschine
unverhältnismässig. Das Distributionspaket bekommt Sicherheitsupdates über die
Paketverwaltung und braucht kein `pip`.

## Die ehrliche Grenze

**Kein Auto-Sync.** Das Gerät browst und importiert manuell: Integration öffnen,
«Meine Dateien» → Bibliothek, Datei antippen.

Für einen Index, den man selten frisch zieht, ist das unerheblich. Wer «Datei abgelegt
= Datei auf dem Tablet» erwartet, erwartet etwas, das die Integration nicht leistet —
und sollte den Rückweg nicht für Zeitkritisches verwenden.

Unbeobachtet ist bis heute, ob ein **erneuter** Import die alte Fassung am Gerät
ersetzt oder eine zweite Kopie anlegt.

## Prüfen

```sh
remarkable_index.py --ausgabe /tmp/index.pdf    # nur lokal, kein Netz
remarkable_index.py --trockenlauf               # erzeugen, nicht hochladen
remarkable_index.py --schreibprobe              # hochladen, lesen, löschen
```
