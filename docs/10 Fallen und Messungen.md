# 10 — Fallen und Messungen

Alles hier ist gemessen, nicht vermutet. Wo eine Annahme widerlegt wurde, steht die
Annahme daneben — sie ist der lehrreichere Teil.

## Die Regel dahinter

**Ein negatives Prüfergebnis braucht eine Referenzmessung gegen einen bekannt positiven
Fall, sonst beweist es nichts.**

«Port zu», «Datei nicht da», «Bibliothek unsichtbar» sehen alle genauso aus wie
«falsch gemessen». Zwei Beispiele weiter unten zeigen, was der Unterschied wert ist.

---

## Microsoft Graph

### Eine Shared Mailbox ist kein Sicherheitsprinzipal

`New-ApplicationAccessPolicy` direkt auf das Postfach scheitert mit «Die Identität des
Richtlinienbereichs ist kein Sicherheitsprinzipal». Der Weg führt über eine
**mail-aktivierte Sicherheitsgruppe** mit dem Postfach als Mitglied.

Fällt bei einem *Benutzer*-Postfach nie auf — das ist einer.

### Die Access Policy greift in Stunden, nicht Minuten

Microsoft nennt «bis zu 30 Minuten», für gruppenbasierte Policies bis zu 24 Stunden.
**Gemessen: rund fünf Stunden.**

In der Zwischenzeit blockt die Policy **auch das eigene, erlaubte Postfach**, weil die
Gruppenmitgliedschaft an der Durchsetzungsschicht noch leer auflöst. Und
`Test-ApplicationAccessPolicy` sagt längst «Gewährt», während der echte Aufruf 403
liefert.

**Das Cmdlet ist nicht die Durchsetzung.** Wer nur ihm glaubt, hält eine Policy für
aktiv, die es nicht ist — in beide Richtungen gefährlich.

### `Sites.Selected` allein gewährt nichts

Die Berechtigung ist nur die Möglichkeit. Ohne `POST /sites/{id}/permissions` antwortet
jeder Zugriff mit 403 — und es gibt **keine Oberfläche** dafür, nur die API.

### `Sites.Selected` erlaubt keine Schema-Änderungen

| Vorgang | Ergebnis |
|---|---|
| Datei hochladen | 200 |
| Spaltenwert setzen | 200 |
| Spalte anlegen | **403** |
| Bibliothek anlegen | **403** `accessDenied` |
| Bibliotheken auflisten | 200 ← **die Referenzmessung** |

Die letzte Zeile ist der Punkt: Sie beweist, dass Token und Weg stimmen. Ohne sie wäre
«403» ebenso gut ein Konfigurationsfehler auf der eigenen Seite gewesen.

### Graph kann Hyperlink-Spalten nicht beschreiben

v1.0, mit Objekt- **und** String-Format geprüft. Die SharePoint-REST-Schnittstelle als
Ausweichweg verlangt Zertifikats-Authentifizierung — mit Client-Secret kommt pauschal
401.

**Folge:** Die Spalte mit dem Vault-Pfad ist eine **Textspalte**. Wer eine Link-Spalte
einplant, baut eine Spalte, die kein Job füllen kann.

### `$select` verwirft die Download-URL

Steht ein `$select` im `driveItem`-Abruf, fehlt `@microsoft.graph.downloadUrl` in der
Antwort. Ohne `$select` ist sie da. Der Abruf läuft deshalb ohne.

Dazu: Der Download läuft **ohne** Authorization-Kopf. Die URL ist kurzlebig
vorauthentifiziert, und die SharePoint-Download-Domain lehnt den Graph-Token ab, wenn
er mitkommt.

### Graph blättert, und `$top` ist eine Bitte

Gemessen an einer Liste mit 35 Zeilen:

```
$top=5     ->  5 Zeilen, nextLink: JA
$top=500   -> 35 Zeilen, nextLink: nein
```

Der zweite Fall ist der Alltag — deshalb fällt es lange nicht auf. Oberhalb der
Seitengrenze lesen Idempotenz-Prüfungen eine Zeile als «nicht vorhanden» und legen sie
**ein zweites Mal an**. Das ist keine Fehlermeldung, das ist eine Dublette.

### SharePoint streicht den Bindestrich

Beim Anlegen einer Bibliothek: `displayName` `an-remarkable` → interner `name`
`anremarkable`. Bei Spalten wird er zu `_x002d_` kodiert. Der Code löst über beide
Namen auf.

---

## Das Gerät

### Die Integration zeigt keine SharePoint-Sites

**Annahme der Vorab-Recherche:** Das Tablet browst SharePoint-Sites direkt.

**Am Gerät gemessen:** Es zeigt **keine** — auch eine seit Tagen bestehende Bibliothek
nicht. *Referenzmessung im selben Lauf: dieselbe Integration zeigt «Meine Dateien»
problemlos.* Es lag an der Sichtbarkeit, nicht an einem Defekt.

**Der Weg:** einmalig «Verknüpfung zu OneDrive hinzufügen» in der Bibliothek. Danach
erscheint sie unter «Meine Dateien».

### Kein Auto-Sync

Das Gerät browst und importiert manuell. Wer «Datei abgelegt = Datei auf dem Tablet»
erwartet, erwartet etwas, das die Integration nicht leistet.

---

## PDF und Text

### Ein PDF ist für `grep` unsichtbar

Ein Wort, das **340-mal** in einem PDF vorkommt, ergab über alle **386 PDFs** eines
Bestands **null Treffer**. Das gilt für normale PDFs genauso wie für Scans.

### Handschrift hat keine Textebene

Getippte Elemente tragen eine echte Textebene. Rein handschriftliche Dokumente liefern
`pdftotext` rc=0 mit leerem Text — **ein echtes Negativ, kein Werkzeugfehler.**

Die Unterscheidung ist wichtig: «nichts gefunden» und «Werkzeug kaputt» sehen im Log
gleich aus, wenn man sie nicht auseinanderhält.

### OCR kostet 13 Sekunden pro Seite

200 dpi, eine vCPU. Bei 70 PDFs sind das mehrere Stunden — daher der Nachlauf mit
Budget statt eines Durchlaufs.

---

## Mail

### Exchange prüft eigene Post nicht

Interne Mail trägt `dkim=none`, `dmarc=none`. **Ein reines DMARC-Gate hätte das eigene
Hauptkonto abgewiesen.**

Der Ersatz: `X-MS-Exchange-Organization-AuthAs: Internal`. Exchange setzt die Zeile
selbst und **entfernt sie an der Organisationsgrenze von jeder Fremdpost** — gemessen:
externe Absender trugen `Anonymous`. Von aussen ist sie nicht mitzubringen.

### `curl` beweist nichts über das Ergebnis

Der Rückgabewert ist 0, sobald *irgendeine* HTTP-Antwort kam — auch bei 401. Geprüft
wird deshalb die Antwort selbst.

Beim ersten Test des Meldekanals meldete der Selbsttest **Erfolg auf ein HTTP 401**,
weil hinter einer Shell-Negation `$?` den negierten Wert trägt. Genau die Klasse
Fehler, gegen die dieser Kanal gebaut wurde.

---

## Betrieb

### Ein Entzug ohne Nachmessung ist eine Absicht, keine Änderung

Zwei Rollen wurden im Portal entzogen. **Acht Tage später standen beide weiterhin im
Token.** Dazu trug das Token eine dritte Rolle, die in keiner Liste stand.

Seither liegt eine Soll-Liste neben dem Code, und ein Job vergleicht sie täglich mit
dem `roles`-Anspruch eines frisch geholten Tokens — **in beiden Richtungen.**

**Das Portal ist nicht das Token.**

### Ein pauschaler Commit nimmt fremde Arbeit mit

Ein gezieltes Hinzufügen von drei Dateien, gefolgt von einem Commit **ohne** Pfadangabe,
ergab einen Commit mit **323 Dateien**. Die übrigen 320 stammten aus einer parallel
laufenden Sitzung.

Inhaltlich ging nichts verloren. Trotzdem ein Schaden: **Ein Rückbau ist dann eine
Suche und kein Befehl.**

### Vier Routinen waren sechs Wochen tot

Ihr Statusbericht lag als Datei da. Wer die Seite nicht öffnet, sieht auch ein rotes
Feld nicht.

**Ein Bericht ist eine Bringschuld des Lesers. Nötig war eine Holschuld des Systems.**

---

## Die Sanitisierung selbst

Auch dieser Schritt hat zwei Fehler produziert, beide durch Trockenlauf und Gegenprobe
gefangen — sie stehen hier, weil sie das Muster zeigen.

### Eine Regel für Prosa traf Code

```python
re.sub(r"\(\s*\)", "", text)     # sollte leere Klammern aus Prosa entfernen
```

Sie machte aus jedem `def postfach():` ein `def postfach:`. **Zehn von zwölf Modulen
liessen sich danach nicht mehr importieren.**

Ebenso `[ \t]{2,} -> " "` gegen doppelte Leerzeichen: Es traf **jede Python-Einrückung**.
Erkannt am unplausiblen Zähler — 413 von 432 Zeilen einer Datei angeblich geändert.

**Eine Regel, die Prosa meint und Code trifft, gehört nicht in einen Textersetzer.**

### Ein Wort steckte in einem anderen

Die Regel «Firmenname → Platzhalter» traf ein ganz normales Fachwort, weil der
Firmenname darin als Substring steckte. Aus einem Fachbegriff wurde ein
Kunstwort, viermal in derselben Datei.

Zum Nachfühlen mit einem erfundenen Namen: Die Firma heisst *Lister*, die Regel
lautet `Lister → Beispiel` — und macht aus **«Al·lister·ung»** ein
«Al·Beispiel·ung». Wortweise Ersetzung ohne Wortgrenzen trifft eben auch Wortteile.

Dieselbe Regel hat später **diesen Absatz hier** getroffen und das Beispiel
unlesbar gemacht. Seither läuft der Sanitisierer nur noch über `src/` und
`tests/` — eine Dokumentation, die über Suchmuster schreibt, enthält sie
zwangsläufig.

### Das Werkzeug hat sich selbst verarbeitet

Der Sanitisierer lag als `.py`-Datei im Verzeichnis, das er durchläuft — und
sanitisierte **seine eigene Ersetzungsliste**. Aus

```python
("ab der Bau dieser Stufe\n", "ab dem Sprachnotiz-Zweig\n")
```

wurde

```python
("ab\n", "ab dem Sprachnotiz-Zweig\n")     # trifft JEDES Zeilenende «ab»
```

Alle anderen Einträge wurden zu Identitätsabbildungen (`("Stufe 1:", "Stufe 1:")`) —
die Liste sah vollständig aus und tat nichts mehr.

Die bereits verarbeiteten Dateien blieben korrekt: Der Lauf hatte die Regeln im
Speicher, als er sie anwandte. Beschädigt war nur die Datei auf der Platte — der
**nächste** Lauf wäre der gefährliche gewesen.

Zwei Konsequenzen: Der Sanitisierer schliesst `werkzeuge/` und `docs/` aus, und die
Muster werden aus einer Variablen zusammengesetzt statt wörtlich hingeschrieben.

**Ein Werkzeug, das seinen eigenen Wirkungsbereich betritt, ändert seine eigenen
Regeln.**

### Und ein dritter, im Messwerkzeug selbst

Der Zähler verglich zwei Dateien mit `zip()`. Sobald eine Zeile entfiel, verglich er ab
da Äpfel mit Birnen und meldete fast alles als geändert. Ersetzt durch `difflib` — plus
eine Warnung, wenn sich die Zeilenzahl überhaupt ändert.

**Ein Messwerkzeug, dem man nicht misstraut, misst irgendwann das Falsche.**

### Die Gegenprobe

```sh
grep -rniE "<firma>|<pfade>|<ticket-praefixe>|<namen>"  src tests   # 0 Treffer
grep -rnoE "[0-9a-f]{8}-[0-9a-f]{4}-…"                        src tests   # 0 GUIDs
grep -rhoE "[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"            src tests   # nur example.com
for t in tests/*.py; do python3 "$t"; done                                 # 5× GRÜN
```

Das Skript liegt bei: [`werkzeuge/sanitisieren.py`](../werkzeuge/sanitisieren.py).
