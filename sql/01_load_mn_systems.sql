-- 01_load_mn_systems.sql
-- Load EPA SDWIS public water systems and keep Minnesota's active community systems.
-- Source: EPA ECHO SDWA download (SDWA_PUB_WATER_SYSTEMS.csv), saved in data/raw/.
-- A "community water system" (CWS) serves the same people year-round, like a city utility.

CREATE OR REPLACE TABLE raw_systems AS
SELECT *
FROM read_csv_auto('data/raw/SDWA_PUB_WATER_SYSTEMS.csv', all_varchar = true);

-- Each system can appear once per quarterly snapshot. Keep only the latest snapshot.
CREATE OR REPLACE TABLE mn_systems AS
SELECT
    PWSID                                          AS pwsid,
    PWS_NAME                                       AS system_name,
    PWS_TYPE_CODE                                  AS system_type,
    PRIMARY_SOURCE_CODE                            AS source_code,
    CASE
        WHEN PRIMARY_SOURCE_CODE LIKE 'GW%' THEN 'Groundwater (wells)'
        WHEN PRIMARY_SOURCE_CODE LIKE 'SW%' THEN 'Surface water (rivers, lakes)'
        WHEN PRIMARY_SOURCE_CODE LIKE 'GU%' THEN 'Groundwater influenced by surface water'
        ELSE 'Other or unknown'
    END                                            AS source_type,
    TRY_CAST(POPULATION_SERVED_COUNT AS INTEGER)   AS population_served,
    CITY_NAME                                      AS city,
    SUBMISSIONYEARQUARTER                          AS snapshot
FROM raw_systems
WHERE STATE_CODE = 'MN'
  AND PWS_ACTIVITY_CODE = 'A'      -- active systems only
  AND PWS_TYPE_CODE = 'CWS'        -- community water systems only
QUALIFY ROW_NUMBER() OVER (PARTITION BY PWSID ORDER BY SUBMISSIONYEARQUARTER DESC) = 1;
