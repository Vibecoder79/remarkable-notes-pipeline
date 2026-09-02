# E-05 — Binaerdokumente durchsuchbar machen

**Status:** entschieden · **Betrifft:** Zuordner, OCR-Nachlauf

## Die Messung, die alles ausloeste

Ein PDF speichert seinen Text komprimiert. **`grep` findet nichts darin, die
Volltextsuche des Notiz-Programms auch nicht** — das gilt fuer ganz normale PDFs
genauso wie fuer Scans.

Gemessen: ein Wort, das 340-mal in einem PDF vorkommt, ergab ueber alle 386 PDFs
eines Bestands **null Treffer**.

## Die Entscheidung

**Zu jedem Binaerdokument entsteht ein Textauszug als Markdown daneben.**

In dieser Strecke wandert der Auszug direkt in die Zeiger-Notiz, als eigener Abschnitt
«Text aus dem Dokument» — als Zitatblock gerahmt
([E-04](E-04%20Fremdinhalt%20ist%20Material,%20nie%20Auftrag.md)) und auf 4'000 Zeichen
gekappt.

Gezogen wird mit `pdftotext`: **deterministisch, ohne Sprachmodell.** Ein Modell
haette hier nichts zu entscheiden — es geht um Zeichen, nicht um Bedeutung.

## Die ehrliche Grenze — der wichtigste Absatz

Erfasst wird **nur die maschinenlesbare Textebene**: getippter, diktierter oder in
Text umgewandelter Inhalt.

**Handschrift ist im PDF-Export eine Vektorzeichnung und bleibt draussen.** Es gibt
hier bewusst kein OCR. Die Trennlinie laeuft also nicht zwischen Geraeten, sondern
**zwischen Tippen und Schreiben**.

Gemessen: getippte Elemente tragen eine echte Textebene, rein handschriftliche
Dokumente liefern `pdftotext` rc=0 mit leerem Text — ein **echtes Negativ**, kein
Werkzeugfehler. Diese Unterscheidung ist wichtig: «nichts gefunden» und «Werkzeug
kaputt» sehen im Log gleich aus, wenn man sie nicht auseinanderhaelt.

Der Satz steht auch **in jeder erzeugten Notiz**. Wer sie liest, soll nicht annehmen,
der Auszug sei vollstaendig.

## Was daraus folgt

- Ein Dokument ohne Auszug ist fuer die Suche unsichtbar. Verlass dich nicht darauf,
  es «schon irgendwie» zu finden.
- Vorhandene Auszuege werden **nie ueberschrieben**, auch handgeschriebene nicht.
- Gescannte PDFs ohne Textebene warten auf den OCR-Nachlauf, der getrennt und mit
  Zeitbudget laeuft.
