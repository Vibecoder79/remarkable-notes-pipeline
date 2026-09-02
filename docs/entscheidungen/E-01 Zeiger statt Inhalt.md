# E-01 — Zeiger statt Inhalt

**Status:** entschieden · **Betrifft:** Zuordner, Ablage-Format

## Die Frage

Ein Tablet schickt ein PDF. Wo lebt dieses PDF danach — im Vault oder im
Dokumentenspeicher?

## Die Entscheidung

**Das Binaerdokument bleibt in der SharePoint-Bibliothek. Im Vault entsteht eine
Notiz, die darauf zeigt.**

Die Notiz traegt `typ: artefakt-zeiger` und im Frontmatter `artefakt: <URL>` — einen
Link nach draussen, keinen Wikilink. Das PDF wird nie ins Vault kopiert.

## Warum

Ein Vault aus Markdown ist durchsuchbar, versionierbar und klein. Sobald Binaerdateien
darin liegen, ist es keines dieser drei mehr: Git speichert jede Fassung vollstaendig,
Volltextsuche findet nichts, und ein Klon dauert Minuten statt Sekunden.

Die naheliegende Gegenrichtung — das Dokument nach Markdown wandeln und im Vault
fuehren — waere schlimmer: Der Inhalt laege dann zweimal vor, und die Kopie altert ab
der ersten neuen Fassung, **ohne dass es auffaellt**. Zwei Wahrheiten sind teurer als
ein Umweg.

## Was daraus folgt

- Die Notiz ist der Knoten fuer Navigation und Verlinkung, das PDF der Inhalt.
- Wer den Wortlaut braucht, folgt dem Link. Wer sucht, sucht in der Notiz.
- Damit die Suche etwas findet, bekommt die Notiz einen Textauszug — siehe
  [E-05](E-05%20Binaerdokumente%20durchsuchbar%20machen.md).

## Was dagegen spricht

Der Link kann brechen. Wird das Dokument in SharePoint verschoben oder geloescht,
zeigt die Notiz ins Leere — und niemand merkt es. Genau deshalb gibt es den Waechter,
der tote `artefakt:`-Links taeglich sucht ([E-06](E-06%20Stille%20bedeutet%20gesund.md)).
Ein bekannter Nachteil mit einer gebauten Antwort ist ein anderer Zustand als ein
uebersehener.
