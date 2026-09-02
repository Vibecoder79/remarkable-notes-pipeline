# Diagramme

Jedes Diagramm liegt zweimal: als `.excalidraw` zum Bearbeiten und als `.svg` zum
Anschauen. **GitHub rendert Excalidraw nicht** — dort sieht man ohne das SVG nur JSON.

Beide entstehen aus derselben Beschreibung:
[`werkzeuge/diagramme_bauen.py`](../../werkzeuge/diagramme_bauen.py). Zwei Fassungen
von Hand zu pflegen hiesse, die zweite altert ab der ersten Änderung.

```sh
python3 werkzeuge/diagramme_bauen.py docs/diagramme
```

Die `.excalidraw`-Dateien lassen sich trotzdem von Hand weiterbearbeiten (in Obsidian
mit dem Excalidraw-Plugin, oder auf excalidraw.com öffnen) — sie sind dann nur nicht
mehr die Quelle.

## Die Farben bedeuten etwas

| Farbe | Bedeutung |
|---|---|
| **blau** | was von aussen kommt — Tablet, Mail, Fremdinhalt |
| **grün** | was der Code tut — Jobs, Prüfungen |
| **gelb** | wo etwas liegt — Postfach, Bibliothek, Vault |
| **rot** | Abweisung, Fehler, Grenze |

## Die fünf Bilder

| Datei | zeigt | gehört zu |
|---|---|---|
| `strecke-gesamt` | der ganze Hinweg, inklusive Selbstheilung | [01 Überblick](../01%20Ueberblick%20—%20die%20Strecke.md) |
| `kuerzel-routing` | wie aus `[ACME]` ein Ordner wird | [02 Vault und Kürzel](../02%20Das%20Vault%20—%20Struktur%20und%20Kuerzel.md) |
| `m365-architektur` | zwei Apps, zwei Grenzen, was gemessen wurde | [03 Microsoft 365](../03%20Microsoft%20365%20—%20die%20Einrichtung.md) |
| `fehlerklassen` | vorübergehend/dauerhaft und die Reihenfolge | [04 Hinweg](../04%20Der%20Hinweg%20—%20vom%20Postfach%20zur%20Notiz.md) |
| `sprachnotiz-leiter` | die 0/1/2+-Leiter und die vier Verteidigungen | [06 Sprachnotiz](../06%20Der%20Sprachnotiz-Zweig%20—%20der%20eine%20Modellaufruf.md) |
