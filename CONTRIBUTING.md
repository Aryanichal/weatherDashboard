# Contributing

## Workflow
1. Create a branch off `main`: `git checkout -b feature/short-description`
2. Commit small, focused changes.
3. Open a pull request into `main` and ask at least one teammate to review.
4. Squash or rebase merge once approved — keep `main` history readable.

## Local setup
See the "Setup" section in [README.md](README.md).

## Code style
- Keep data-fetching (`src/data_loader.py`), analysis (`src/analysis.py`), and
  UI (`app.py`) separated so the app stays easy to extend.
- Don't commit anything under `data/` (it's git-ignored) — it's re-downloaded
  or regenerated locally via `src/data_loader.py`.
- Prefer small, composable functions in `src/` over logic embedded directly
  in `app.py`, so analysis code is testable outside of Streamlit.
