# Kleinanzeigen active-search PUKÖ cycles

## 1. Search coverage

- **Plan:** Improve recall without allowing unbounded scraping.
- **Do:** Add focused, balanced and broad query coverage. Balanced mode keeps profile phrases, interleaves German market aliases and adds full/part-time variants.
- **Check:** Query generation is deduplicated and capped by `max_search_terms`.
- **Act:** Use balanced coverage as the default and retain focused mode for exact profiles.

## 2. Detail completeness

- **Plan:** Spend the detail-page budget where it improves analysis most.
- **Do:** Prioritize cards missing a useful description, employer, location, date or employment signal.
- **Check:** Unit tests verify incomplete cards are enriched first.
- **Act:** Raise the new-source default detail budget to 20 while keeping the hard limit and request delay.

## 3. Data categorization

- **Plan:** Turn provider text into consistent decision metadata.
- **Do:** Classify role family, job level, employment type, weekly hours, shift, postal code, publication age and data completeness.
- **Check:** Deterministic tests cover a German quality-technician ad and incomplete metadata.
- **Act:** Derive metadata when serving stored jobs so existing databases need no destructive migration.

## 4. Freshness and active status

- **Plan:** Keep inactive and stale ads out of the active review flow.
- **Do:** Preserve the 7/30/90-day source filter, parse German relative dates, remove explicitly inactive detail pages and expose freshness on every card.
- **Check:** Existing provider tests cover relative dates, known-old ads and unknown-date preservation.
- **Act:** Default to the last 30 days; unknown dates remain visible rather than being falsely rejected.

## 5. Decision-focused job cards

- **Plan:** Reduce the time needed to judge an ad.
- **Do:** Show category, employment type, hours/shift, freshness, job level, data completeness, description preview, publication date and postal code alongside existing fit and language scores.
- **Check:** UI regression tests require every new card field; JavaScript syntax and full application tests run in CI.
- **Act:** Keep detailed scoring reasons compact while promoting decision-critical metadata above the scores.
