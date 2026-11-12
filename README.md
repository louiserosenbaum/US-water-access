# U.S. Water Access

**Status: In progress.** First public version (interactive map) planned for January 31, 2027.

## The question

Why does tap water look, smell, and feel so different from place to place, who is responsible for it, and where are people least protected?

## Why it matters

Safe drinking water has been recognized as a human right by the United Nations since 2010. In the U.S., the Safe Drinking Water Act sets enforceable health limits for public water systems, but taste, smell, and hardness are left to local utilities, and private wells are not covered by federal rules at all.

## Findings so far: Minnesota

![Share of systems vs. share of people on wells](images/wells_vs_people.png)

95% of Minnesota's 1,000 active community water systems run on wells, but 49 river and lake systems serve nearly a third of the people (1.5 million). Most of the state's remaining residents likely rely on private wells, which federal drinking water rules do not cover. That gap is the next thing to check.

![Small-system violation rates, tribal vs. state-regulated](images/small_system_violations.png)

Tribal water systems in Minnesota are regulated by the EPA, not the state, and use a different ID format. My first query left them out by accident. With them included, and comparing small systems (under 500 people) to small systems, tribal systems were about 2.7x as likely to have a recorded health-based violation in the last five years. The other size groups have too few tribal systems (1 to 4) to compare.

**Limits:** 9 of 35 is a small number, and differences in how the EPA and the state monitor and record violations could explain part of the gap. This shows where to look, not a cause.

**Watch the totals:** one violation at Saint Paul Regional Water Services (392,529 people) makes it look like hundreds of thousands were affected. And Inver Grove Heights' ongoing radium problem appears as 22 separate quarterly violations. Counts of systems, not people or violations, give the fairer picture.

## How to run

1. Download the SDWA data from [EPA ECHO Data Downloads](https://echo.epa.gov/tools/data-downloads) and put `SDWA_PUB_WATER_SYSTEMS.csv` in `data/raw/`.
2. `pip install duckdb`
3. `python3 build.py`
4. `pip install matplotlib`, then `python3 charts.py` to redraw the charts

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
