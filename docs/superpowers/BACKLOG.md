# bbterm — Backlog

Ordered list of remaining work. Top = next. Shipped phases are recorded in
`specs/` and git history.

## Done
- Phases 1–4: charts, watchlist, DES stats, FA fundamentals, FIL filings.
- Packaging Phase 1: public OSS release, AGPL, pipx (`v0.1.0`).
- Packaging Phase 2: PyPI publish as `bbterm-tui` (`v0.1.1`).

## Next
1. **News feed** — in design now.
2. **Private advanced fork** — strategic, later.

## Deferred (do last, after everything above)
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
