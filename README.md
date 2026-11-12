# U.S. Water Access

**Status: In progress.** First public version (interactive map) planned for January 31, 2027.

## The question

Why does tap water look, smell, and feel so different from place to place, who is responsible for it, and where are people least protected?

## Why it matters

Safe drinking water has been recognized as a human right by the United Nations since 2010. In the U.S., the Safe Drinking Water Act sets enforceable health limits for public water systems, but taste, smell, and hardness are left to local utilities, and private wells are not covered by federal rules at all.

## First finding: Minnesota

Active community water systems (city and town utilities), from EPA SDWIS:

| Source | Systems | People served |
|---|---|---|
| Groundwater (wells) | 948 | 3,214,116 |
| Surface water (rivers, lakes) | 49 | 1,485,877 |
| Groundwater influenced by surface water | 3 | 43,675 |

95% of Minnesota's community systems run on wells, but 49 surface-water systems serve nearly a third of the people. These systems serve about 4.7 million Minnesotans. Most of the rest of the state likely relies on private wells, which federal drinking water rules do not cover. That gap is the next thing to check.

## How to run

1. Download the SDWA data from [EPA ECHO Data Downloads](https://echo.epa.gov/tools/data-downloads) and put `SDWA_PUB_WATER_SYSTEMS.csv` in `data/raw/`.
2. `pip install duckdb`
3. `python3 build.py`

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
