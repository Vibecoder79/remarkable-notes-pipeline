# E-08 — Kuerzel in eckigen Klammern als Anker

**Status:** entschieden · **Betrifft:** das gesamte Routing — `kuerzel_register.py`

## Die Frage

Ein Dokument kommt an. Zu welchem Vorgang gehoert es?

## Was nicht geht — und warum

Der naheliegende Weg waere, es aus dem Inhalt zu erschliessen: Teilnehmer, Domaenen
im Text, Kalendereintraege, Aehnlichkeit zu bestehenden Notizen.

Das scheitert an der Quelle. Eine Mail vom Tablet traegt **keine** Teilnehmer, keine
Sprachangabe, keine Tags und keinen Kalenderbezug — nur Betreff, Rumpf und Anhang.
Und ein Modell auf den Inhalt anzusetzen hiesse raten zu lassen, wo es nichts zu
verstehen gibt.

## Die Entscheidung

**Der Mensch setzt beim Erstellen ein Kuerzel in eckigen Klammern an den Anfang des
Namens:**

```
[ACME] Zonenskizze              -> Dokumentname auf dem Tablet
[ACME] NOTIZ Zonenskizze        -> Sprachnotiz zur selben Sache
[VTR-ACME] Angebotsgespraech    -> ein Lead statt eines Projekts
[P-MUSTER-M] Jahresgespraech    -> eine Person
```

Das ist **Zeichenvergleich, kein Verstehen** — und gehoert deshalb in ein Programm,
nicht in ein Modell.

## Das Register kommt aus dem Vault, nicht aus einer Liste

Jeder Hub traegt sein Kuerzel im Frontmatter (`meeting_key` oder `lead_key`).
`kuerzel_register.py` liest bei **jedem Lauf** alle Baeume durch und baut daraus das
Register.

**Es gibt bewusst keine zweite gepflegte Kuerzelliste.** Zwei Listen driften
auseinander, und dann ist unklar, welche gilt. Das Vault ist der Index.

## Die fuenf Baeume

| Baum | Praefix | wofuer |
|---|---|---|
| `02 Projekte` | keines | Vorhaben mit Ziel und Enddatum |
| `09 Vertrieb` | `VTR-` | alles vor dem Auftrag |
| `10 Personen` | `P-` | Menschen mit eigenen Gespraechen |
| `04 Ressourcen/Persoenliche Notizen` | `PN-` | Themen ohne Projektcharakter |
| `03 Bereiche` | keines | laufende Verantwortung ohne Enddatum |

Das Register ist **struktur-blind**: Es liest jede `.md` mit einem Schluessel, gleich
in welchem Baum sie liegt. Ein Baum, der nicht in der Liste steht, ist unsichtbar —
und seine Kuerzel laufen ins Leere, ohne dass jemand einen Fehler sieht. Wer einen
Baum hinzufuegt, aendert **eine Konstante**.

## Es wird nie geraten

```
kein Kuerzel im Namen        -> keine Zuordnung
Kuerzel nicht im Register    -> keine Zuordnung
Kuerzel ist Praefix eines anderen (mehrdeutig) -> keine Zuordnung
Kuerzel klein geschrieben    -> keine Zuordnung
Kuerzel nicht am Anfang      -> keine Zuordnung
```

Weder ueber Aehnlichkeit noch ueber Teiltreffer. **Ein unbekanntes Kuerzel ist ein
Befund, keine Einladung zur Interpretation.**

## Die Selbstheilung

Ein Dokument ohne gueltiges Kuerzel geht **nicht verloren**. Es bleibt auf
`Status = Neu` und erscheint in der Ansicht «Ohne Zuordnung». Repariert wird durch
**Umbenennen der Datei** — der naechste Lauf holt die Notiz nach.

Ein eigener Nachlauf ist dafuer nicht noetig: Der Zuordner geht diese Eintraege bei
jedem Lauf erneut durch. Das faellt aus dem Design.

## Der Preis, ehrlich

Die einzige echte Schwachstelle der Strecke ist der **Tippfehler beim Kuerzel** am
Geraet. Dagegen laeuft der Rueckweg
([E-11](E-11%20Der%20Rueckweg%20—%20ein%20Index%20aufs%20Geraet.md)): ein
Nachschlage-Zettel mit allen vergebenen Kuerzeln, der auf dem Tablet liegt.
