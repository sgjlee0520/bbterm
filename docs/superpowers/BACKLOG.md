# bbterm — Backlog

Ordered list of remaining work. Top = next. Shipped phases are recorded in
`specs/` and git history.

## Done
- Phases 1–4: charts, watchlist, DES stats, FA fundamentals, FIL filings.
- Packaging Phase 1: public OSS release, AGPL, pipx (`v0.1.0`).
- Packaging Phase 2: PyPI publish as `bbterm-tui` (`v0.1.1`).
- News feed: per-symbol headlines via Google News RSS (`N` command), merged to
  `main` 2026-06-20 (PR #3).

## Next — private / advanced (for myself)
A private build is the natural home for these (my data, my edge). Not yet designed
— each gets the brainstorming → spec → plan flow when picked up.

1. **Portfolio tracker** — enter my holdings + cost basis; show total value, daily
   gain/loss, and best/worst positions at a glance.
2. **Smart alerts** — background watch that notifies me on price moves or news
   (e.g. "ping me if AAPL drops below $200", "alert on big NVDA news").
3. **Obsidian decision-notes vault** — save my investing notes/decisions as
   markdown into an Obsidian vault: things like the Magic Formula from *The Little
   Book That Still Beats the Market*, my future predictions, and the rationale
   behind picks. bbterm reads/writes plain `.md` files in a vault folder.

Considered, not chosen:
- **Live/real-time prices** — would need a paid data feed (current data is ~15-min
  delayed, end-of-day charts). Open question, not committed.
- **AI market assistant** — declined; I use my own formula/method.

## Deferred (do last, after everything above)
4. **Homebrew tap** — `brew install bbterm` on Apple Silicon macOS.
3. **Homebrew tap** — `brew install bbterm` on Apple Silicon macOS.
   - Decided during brainstorming (2026-06-20): **personal tap**
     `sgjlee0520/homebrew-bbterm`, formula named `bbterm`, **wheel-vendoring**
     approach (Approach A) — vendor prebuilt arm64-macOS wheels and install
     offline, **no source builds, no bottle pipeline**. arm64 current-macOS only.
   - Deferred because the formula's offline-wheel install step is an
     unpredictable time sink for a third install channel (pipx already works).
     Low effort/value ratio vs. product features above.
   - Resume from: the design notes in this session's brainstorming; re-run the
     brainstorming → spec → plan flow when picked up.
