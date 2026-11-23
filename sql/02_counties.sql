-- 02_counties.sql
-- Find the county each Minnesota water system serves, so systems can go on a map.
-- Source: SDWA_GEOGRAPHIC_AREAS.csv. AREA_TYPE_CODE 'CN' means a county record.

CREATE OR REPLACE TABLE mn_system_counties AS
SELECT DISTINCT
    PWSID                    AS pwsid,
    TRIM(COUNTY_SERVED)      AS county
FROM read_csv_auto('data/raw/SDWA_GEOGRAPHIC_AREAS.csv', all_varchar = true)
WHERE PWSID IN (SELECT pwsid FROM mn_systems)
  AND AREA_TYPE_CODE = 'CN'
  AND COUNTY_SERVED IS NOT NULL;

-- A few systems serve more than one county. To avoid counting the same people twice,
-- give each system one home county (the first alphabetically) for county totals.
CREATE OR REPLACE TABLE mn_systems_with_county AS
-- Tribal water systems in Minnesota are regulated by EPA Region 5, not the state.
-- Their IDs start with '05' instead of 'MN', and their geography records use tribal
-- areas instead of counties, so flag them instead of leaving them as unknown.
SELECT
    s.*,
    c.county,
    s.pwsid LIKE '05%' AS is_tribal_epa_regulated
FROM mn_systems AS s
LEFT JOIN (
    SELECT pwsid, MIN(county) AS county
    FROM mn_system_counties
    GROUP BY pwsid
) AS c USING (pwsid);

CREATE OR REPLACE TABLE mn_county_summary AS
SELECT
    county,
    COUNT(*)                                                       AS systems,
    SUM(population_served)                                         AS people_served,
    SUM(CASE WHEN source_type LIKE 'Groundwater (wells)' THEN population_served ELSE 0 END)
        / NULLIF(SUM(population_served), 0)                        AS share_on_wells
FROM mn_systems_with_county
GROUP BY county;
