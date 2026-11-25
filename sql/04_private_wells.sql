-- 04_private_wells.sql
-- Estimate how many people in each Minnesota county are NOT on a community water system.
-- Most of them get water from a private well, which federal drinking water rules don't cover.
--
-- Method: county population (Census) minus people served by community systems in that county.
-- Source: Census Vintage 2025 county estimates, data/raw/co-est2025-alldata.csv
--   https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv
-- Note: the Census file is Latin-1, not UTF-8 (accented names like "Doña Ana County"),
-- so it has to be read with encoding = 'latin-1'.
--
-- Limits (also in the README):
--   * It's an estimate. Some of these people are on small non-community systems
--     (mobile home parks, some businesses), not private wells.
--   * Each water system counts in one home county, but some serve several. Where a big
--     system's customers spill over a county line, the estimate for that county can go
--     below zero; those are set to 0 and flagged.
--   * Tribal systems have no county in the EPA data, so the ~51,000 people they serve
--     aren't subtracted from any county.

CREATE OR REPLACE TABLE mn_county_population AS
SELECT
    REPLACE(CTYNAME, ' County', '')        AS county,
    COUNTY                                 AS county_fips,
    TRY_CAST(POPESTIMATE2025 AS INTEGER)   AS population_2025
FROM read_csv('data/raw/co-est2025-alldata.csv',
              header = true, all_varchar = true, encoding = 'latin-1')
WHERE STNAME = 'Minnesota'
  AND SUMLEV = '050';   -- 050 = county rows (040 is the state total)

CREATE OR REPLACE TABLE mn_private_wells AS
SELECT
    p.county,
    p.population_2025,
    COALESCE(s.people_served, 0)                                        AS community_served,
    GREATEST(p.population_2025 - COALESCE(s.people_served, 0), 0)       AS est_not_on_community,
    ROUND(100.0 * GREATEST(p.population_2025 - COALESCE(s.people_served, 0), 0)
          / p.population_2025, 1)                                       AS pct_not_on_community,
    COALESCE(s.people_served, 0) > p.population_2025                    AS served_exceeds_population
FROM mn_county_population AS p
LEFT JOIN mn_county_summary AS s
       ON LOWER(s.county) = LOWER(p.county);
