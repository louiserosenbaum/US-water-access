# U.S. Water Access

**Status: In progress.** First public version (interactive map) planned for January 31, 2027.

## The question

Why does tap water look, smell, and feel so different from place to place, who is responsible for it, and where are people least protected?

## Why it matters

Safe drinking water has been recognized as a human right by the United Nations since 2010. In the U.S., the Safe Drinking Water Act sets enforceable health limits for public water systems, but taste, smell, and hardness are left to local utilities, and private wells are not covered by federal rules at all.

## Plan

| Phase | What ships | Target |
|---|---|---|
| 1 | Minnesota and national data joined in DuckDB; interactive map on GitHub Pages | Jan 31, 2027 |
| 2 | State rules table, every row sourced and dated | Feb 28, 2027 |
| 3 | Daily data refresh | Mar 31, 2027 |

## Data sources (Phase 1)

- **EPA Safe Drinking Water Information System (SDWIS):** public water systems, their sources, and violations
- **USGS:** water hardness by location
- **Minnesota Department of Health:** private well data

## Tools

SQL (DuckDB) for loading, cleaning, and joining. Python for the interactive map.

## Notes

This project is informational. It cites its sources and is not a health or legal authority.
