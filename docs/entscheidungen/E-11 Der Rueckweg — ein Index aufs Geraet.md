# E-11 — Der Rueckweg: ein Index aufs Geraet

**Status:** entschieden · **Betrifft:** `remarkable_index.py`

## Die Frage

Die Strecke haengt daran, dass der Mensch am Geraet das richtige Kuerzel tippt
([E-08](E-08%20Kuerzel%20in%20eckigen%20Klammern%20als%20Anker.md)). Ein Tippfehler ist
die einzige echte Schwachstelle. Wie kommt die Kuerzelliste auf das Tablet?

## Die Entscheidung

**Ein naechtlich erzeugter PDF-Index in einer eigenen Bibliothek**, die der Eigner
einmalig mit seinem Cloud-Speicher verknuepft. Das Geraet browst dort und importiert
die Datei von Hand.

```
Job ──Sites.Selected──> Bibliothek 'an-remarkable'
                              │
                              │ Verknuepfung zum Cloud-Speicher
                              │ (einmalig, von Hand)
                              v
                    «Meine Dateien» des Eigners
                              │ Tablet-Integration, Anmeldung am Geraet
                              v
                    Tablet: browse + tap (manueller Import)
```

## Drei Auflagen

1. **Eigene Bibliothek**, getrennt von der Abhol-Bibliothek — sonst vermischen sich
   Hin- und Rueckweg. Flach, keine Spalten: sie ist ein Ablagefach, kein Arbeitsvorrat.
2. **Stabiler Dateiname.** Jeder Lauf ueberschreibt dieselbe Datei; am Geraet ist es
   immer die aktuelle. Nach dem Upload wird die Groesse **zurueckgelesen** — erst der
   Nachweis macht den Upload zum Ergebnis.
3. **Dieselbe Quelle wie der Zuordner.** Der Index zeigt exakt das, was die Strecke
   versteht. Eine zweite Kuerzelliste gaebe es sonst doch.

## Zwei gemessene Befunde, die Annahmen widerlegt haben

**Das Geraet zeigt keine SharePoint-Sites.** Die Vorab-Recherche nahm an, die
Integration browse Sites direkt. Am Geraet gemessen: die Integration zeigt **keine** —
auch eine seit Tagen bestehende Bibliothek nicht. Der gangbare Weg fuehrt ueber die
**Verknuepfung zum Cloud-Speicher**; danach erscheint sie unter «Meine Dateien».
*(Referenzmessung im selben Lauf: dieselbe Integration zeigt «Meine Dateien» — es lag
also an der Sichtbarkeit, nicht an einem Defekt.)*

**Kein Auto-Sync.** Das Geraet browst und importiert **manuell**. Wer «Datei abgelegt
= Datei auf dem Tablet» erwartet, erwartet etwas, das die Integration nicht leistet.
Fuer einen Index, den man selten frisch zieht, ist das unerheblich — fuer andere
Anwendungen waere es der entscheidende Punkt.

## Fehlerbild, mit Absicht anders als beim Abholer

| Lage | Klasse | warum |
|---|---|---|
| Bibliothek fehlt | **voruebergehend** | Die Anlage von Hand ist der geplante Weg; der erste Lauf danach heilt ohne Zutun |
| Register leer | **dauerhaft** | Ein leerer Index waere eine Antwort, die wie eine Antwort aussieht und keine ist |

Beim Abholer ist eine fehlende Bibliothek dagegen **dauerhaft**: dort ist sie der
Konfigurationsbruch einer laufenden Strecke.

## Werkzeugwahl

PDF-Erzeugung mit **fpdf2** aus dem Distributionspaket. Es ist die kleinste
Abhaengigkeit, die Unicode-Schriften einbetten kann — die Ordnernamen tragen Umlaute,
und der eingebaute Latin-1-Zeichensatz von PDF reicht dafuer nicht. Ein
Office-Renderer oder ein Browser waere auf einer kleinen Maschine unverhaeltnismaessig.
