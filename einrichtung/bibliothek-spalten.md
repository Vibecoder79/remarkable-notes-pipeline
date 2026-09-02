# Die Bibliothek: Spalten und Ansichten

Von Hand anzulegen — `Sites.Selected` erlaubt keine Schema-Änderungen (403).

## Bibliothek `remarkable` (Hinweg)

Flach, keine Ordner. Fünf Spalten:

| Anzeigename | Typ | interner Name | wer schreibt |
|---|---|---|---|
| Projekt | Text, einzeilig | `Projekt` | Zuordner |
| Status | Auswahl: Neu / Verarbeitet / Fehler — **Standard: Neu** | `Status` | Abholer, Zuordner |
| Kontext | Text, mehrzeilig | `Kontext` | Abholer |
| Vault-Notiz | **Text**, einzeilig | `Vault_x002d_Notiz` | Zuordner |
| Eingang | Datum **und Uhrzeit** | `Eingang` | Abholer |

> `Vault-Notiz` ist eine **Textspalte**, obwohl ein Pfad darinsteht. Graph kann
> Hyperlink-Spalten nicht beschreiben. Wer hier eine Link-Spalte einplant, baut eine
> Spalte, die kein Job füllen kann.

> Der Bindestrich wird im internen Namen zu `_x002d_` kodiert. Beim Anlegen einer
> Bibliothek streicht SharePoint ihn ganz (`an-remarkable` → `anremarkable`).

### Drei Ansichten

| Name | Filter | wozu |
|---|---|---|
| Neu | `Status = Neu` | was noch aussteht |
| Nach Projekt | gruppiert nach `Projekt` | Überblick |
| **Ohne Zuordnung** | `Projekt` ist leer, Spalte `Kontext` einblenden | **die Arbeitsliste** |

Die dritte ist die wichtigste: Dort landet, was kein gültiges Kürzel trug. Repariert
wird durch **Umbenennen der Datei** — nie über die Spalten, sonst entstehen zwei
Wahrheiten.

## Bibliothek `an-remarkable` (Rückweg)

Flach, **keine Spalten, keine Ansichten**. Ein Ablagefach, kein Arbeitsvorrat.

Nach dem Anlegen einmalig **«Verknüpfung zu OneDrive hinzufügen»** klicken — ohne
diesen Schritt sieht das Tablet die Bibliothek nicht.

## Schreibprobe vor der Inbetriebnahme

Testdatei hochladen, **alle fünf Spalten setzen**, lesen, löschen. Erst wenn die
Spalten schreibbar sind, trägt die Bibliothek.
