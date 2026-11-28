-- 06_national_tribal.sql
-- Does Minnesota's tribal vs. state gap hold nationally?
-- Compares small (under 500 people) active community water systems: tribal systems that
-- EPA regulates directly vs. state-regulated systems, within each EPA region.
-- Navajo Nation runs its own program (IDs start 'NN'), so it is kept out of the EPA-tribal group.
-- Territories are left out.
-- Region, not state: STATE_CODE is the owner's mailing state, so it can't place tribal systems.
-- Source: EPA ECHO SDWA download (national files) in data/raw/.

CREATE OR REPLACE TABLE us_systems AS
SELECT PWSID AS pwsid, PRIMACY_TYPE AS primacy, EPA_REGION AS region,
       TRY_CAST(POPULATION_SERVED_COUNT AS INTEGER) AS population_served
FROM read_csv('data/raw/SDWA_PUB_WATER_SYSTEMS.csv', all_varchar = true)
WHERE PWS_ACTIVITY_CODE = 'A' AND PWS_TYPE_CODE = 'CWS'
QUALIFY ROW_NUMBER() OVER (PARTITION BY PWSID ORDER BY SUBMISSIONYEARQUARTER DESC) = 1;

-- One row per health-based violation (the raw file repeats violations once per enforcement action).
CREATE OR REPLACE TABLE us_health_violations AS
SELECT DISTINCT PWSID AS pwsid, VIOLATION_ID AS violation_id,
       TRY_STRPTIME(NON_COMPL_PER_BEGIN_DATE, '%m/%d/%Y')::DATE AS began
FROM read_csv('data/raw/SDWA_VIOLATIONS_ENFORCEMENT.csv', all_varchar = true)
WHERE IS_HEALTH_BASED_IND = 'Y';

CREATE OR REPLACE TABLE us_small AS
SELECT s.pwsid, s.region,
       CASE WHEN s.primacy = 'Tribal' THEN 'tribal_epa' ELSE 'state' END AS grp,
       EXISTS (SELECT 1 FROM us_health_violations v
               WHERE v.pwsid = s.pwsid AND v.began >= CURRENT_DATE - INTERVAL 5 YEAR) AS has_violation
FROM us_systems s
WHERE s.population_served < 500
  AND (s.primacy = 'State' OR (s.primacy = 'Tribal' AND s.pwsid NOT LIKE 'NN%'));

CREATE OR REPLACE TABLE us_tribal_by_region AS
SELECT region,
       COUNT(*) FILTER (grp = 'tribal_epa')                          AS tribal_systems,
       COUNT(*) FILTER (grp = 'tribal_epa' AND has_violation)        AS tribal_with_violation,
       COUNT(*) FILTER (grp = 'state')                               AS state_systems,
       COUNT(*) FILTER (grp = 'state' AND has_violation)             AS state_with_violation
FROM us_small
GROUP BY region
HAVING COUNT(*) FILTER (grp = 'tribal_epa') > 0
ORDER BY region;
