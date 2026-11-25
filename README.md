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

## Automatic timetable updates

Every Monday a GitHub Actions job (`.github/workflows/update-timetable.yml`) runs `scripts/update_timetable.py`, which:

- downloads the latest Envibus open-data timetable (GTFS, from data.gouv.fr) and extracts line 11 between the gare routière and Collège du Rouret / Les Trucs, for each weekday;
- finds the current 26S and 27S timetable PDFs on their envibus.fr line pages and reads the afternoon return times;
- writes `data/timetable.json`, which the page loads. If anything changed, the job saves it here and GitHub Pages republishes.

If a download fails, the file looks out of date, or the timetable can't be read, the job stops without changing anything and GitHub emails you that the run failed. You can also run it by hand from **Actions → Update bus timetable → Run workflow**.

The times written in `index.html` are only a fallback for when `data/timetable.json` can't be loaded.

Cistes and Moulins times for 27S are not printed on its sheet; they are estimated as Place du Rouret + 4 minutes (marked ≈ on the page).
