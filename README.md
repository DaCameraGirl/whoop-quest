# WHOOP Quest 💖

Your WHOOP stats → a living goal game.

Every day your WHOOP recovery, sleep, and heart rate feed into your character. Good days level you up. Rough days? Your little buddy feels it too.

Built for Angela / @DaCameraGirl

---

## How it works

| WHOOP stat | Game stat | Good range |
|---|---|---|
| Recovery Score | ❤️ HP | ≥67% = full health |
| Sleep Hours | 💤 Energy | 7–9h = fully charged |
| RHR | ⚡ Calm | ≤75 bpm = zen mode |
| HRV | ✨ Power | higher = stronger |

- **Green recovery day (67%+)** → +XP, streak bonus, unlock skins
- **Yellow (34-66%)** → steady, maintain
- **Red (<34%)** → rest day, no penalty, just cozy mode
- **7-day rolling average** drives your rank
- **Workouts** = bonus XP (strain × 10)

Your character evolves over time as more WHOOP data flows in.

---

## Live App

[Play WHOOP Quest →](https://dacameragirl.github.io/whoop-quest/)

---

## Auto-sync

A GitHub Action runs daily at 9am ET, pulling fresh WHOOP stats via the WHOOP API and updating `data/whoop.json`. The app reads that file — no backend needed.

To set up for your own WHOOP account, see [SETUP.md](SETUP.md).

---

## Tech

- Frontend: vanilla HTML/CSS/JS + Chart.js — no build step, ships on GitHub Pages
- Data: `data/whoop.json` — auto-updated daily via GitHub Actions
- WHOOP API: real WHOOP Developer API, read-only scopes

---

## License

MIT
