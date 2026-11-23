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
-- Which systems are in Minnesota: STATE_CODE is the owner's mailing state, NOT where the
-- water system is. A Wisconsin mobile home park with a Minneapolis owner has STATE_CODE 'MN'.
-- So go by the ID instead: 'MN' IDs are regulated by Minnesota, and '05' IDs are regulated
-- by EPA Region 5 (tribal systems). Region 5 covers six states, so for '05' IDs we still
-- need STATE_CODE to keep only Minnesota's.
WHERE (PWSID LIKE 'MN%' OR (PWSID LIKE '05%' AND STATE_CODE = 'MN'))
  AND PWS_ACTIVITY_CODE = 'A'      -- active systems only
  AND PWS_TYPE_CODE = 'CWS'        -- community water systems only
QUALIFY ROW_NUMBER() OVER (PARTITION BY PWSID ORDER BY SUBMISSIONYEARQUARTER DESC) = 1;
