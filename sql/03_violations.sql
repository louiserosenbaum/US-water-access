-- 03_violations.sql
-- Count health-based violations per Minnesota water system over the last 5 years.
-- Source: SDWA_VIOLATIONS_ENFORCEMENT.csv (a very large national file, so filter while reading).
--
-- Watch out: this file has one row per violation AND enforcement action.
-- One violation with three enforcement actions appears three times,
-- so count DISTINCT VIOLATION_ID, not rows.

CREATE OR REPLACE TABLE mn_violations AS
SELECT DISTINCT
    PWSID                                                       AS pwsid,
    VIOLATION_ID                                                AS violation_id,
    VIOLATION_CATEGORY_CODE                                     AS category,
    RULE_FAMILY_CODE                                            AS rule_family,
    VIOLATION_STATUS                                            AS status,
    TRY_STRPTIME(NON_COMPL_PER_BEGIN_DATE, '%m/%d/%Y')::DATE    AS began
FROM read_csv_auto('data/raw/SDWA_VIOLATIONS_ENFORCEMENT.csv', all_varchar = true)
WHERE PWSID IN (SELECT pwsid FROM mn_systems)   -- includes EPA-regulated tribal systems
  AND IS_HEALTH_BASED_IND = 'Y';

CREATE OR REPLACE TABLE mn_system_violations AS
SELECT
    s.pwsid,
    s.system_name,
    s.county,
    s.source_type,
    s.population_served,
    s.is_tribal_epa_regulated,
    COUNT(DISTINCT v.violation_id)                                        AS health_violations_5yr,
    COUNT(DISTINCT CASE WHEN v.status = 'Unaddressed' THEN v.violation_id END) AS unaddressed
FROM mn_systems_with_county AS s
LEFT JOIN mn_violations AS v
    ON v.pwsid = s.pwsid
   AND v.began >= CURRENT_DATE - INTERVAL 5 YEAR
GROUP BY ALL;
