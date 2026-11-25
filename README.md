# Home from CIV

A weekly overview of how Sarah and Alara get home from the Lycée International de Valbonne (CIV) to Le Rouret: which bus, where to get off, when to walk, when an Icilà shuttle helps, and when there is a car pick-up.

- **Live, shared version (claude.ai):** https://claude.ai/artifact/PEm9QoJ6rBJfPVMbbq4J5b. Changes to "school ends" are shared with everyone who has access. Signing in to Claude is required.
- **Public copy (GitHub Pages):** works without an account. Changes to "school ends" are saved only on the device where they are made.

## What's in it

`index.html` is the whole app: plain HTML, CSS and JavaScript, no build step.

- Usual finishing times per girl, for week A and week B (`ENDS`).
- School lines 26S and 27S, and line 11 departures from the gare routière (`SCHOOL`, `L11`).
- `route()` picks the trip home for a finishing time: school bus and walk first, then line 11 + Icilà, then line 11 + car pick-up at Collège du Rouret, then a car pick-up at the CIV.
- Week letters alternate A/B over school weeks, starting with week B on 30 November 2026; holidays are skipped.

## Updating

Bus times are for the 2026–2027 school year: the line 11 timetable is valid from 31 August 2026 to 4 July 2027, and the 26S and 27S sheets from September 2026. Envibus usually changes them once a year, for the new school year. When Envibus publishes new times, update `SCHOOL` and `L11`, and add new school holidays to `holidays`.
