# E-10 — Jedes Werkzeug ist dokumentiert, in drei Ebenen

**Status:** entschieden · **Betrifft:** jeden Beitrag zu dieser Strecke

## Die Entscheidung

**Wer baut, dokumentiert im selben Zug.** Drei Ebenen, alle drei:

| Ebene | Beantwortet | Wo |
|---|---|---|
| **Architektur** | Wie ist es gebaut? | `docs/` |
| **Benutzung** | Wie benutze ich es? | `docs/09 Nachbau` und die Handbuch-Abschnitte |
| **Code** | Warum steht die Zeile so da? | Docstring im Programm |

## Warum die dritte Ebene die wichtigste ist

Sie wird am ehesten vergessen und richtet den groessten Schaden an.

**Ein fehlender Handbuch-Abschnitt ist eine Luecke. Ein Docstring, der gegen den Code
steht, ist eine Falschaussage** — und er wird geglaubt, weil er daneben steht.

## Der Stil, der hier gilt

Die Docstrings dieser Strecke sind ungewoehnlich lang, und das ist Absicht. Sie
beantworten nicht «was tut die Funktion» — das steht im Code —, sondern:

- **Warum steht das hier und nicht woanders?**
- **Was wurde gemessen, und wann?**
- **Welche naheliegende Alternative wurde verworfen, und woran ist sie gescheitert?**

Ein Beispiel aus `graph_alle()`: Die Funktion holt eine Liste ueber alle Seiten. Der
Docstring erklaert, dass `$top` eine Bitte und keine Zusage ist, zeigt die Messung
(`$top=5` liefert 5 Zeilen und einen `nextLink`) und benennt die Folge — dass
Idempotenz-Pruefungen eine Zeile hinter der Seitengrenze als «nicht vorhanden» lesen
und **eine Dublette anlegen**. Das ist keine Fehlermeldung, das ist ein stiller
Datenfehler.

Diese drei Absaetze verhindern, dass jemand die Paginierung «vereinfacht».

## Die Pflicht greift, wenn sich Verhalten aendert, das jemand von aussen sieht

Nicht bei Tippfehlern, nicht bei Formatierung. **Im Zweifel gilt sie.**
