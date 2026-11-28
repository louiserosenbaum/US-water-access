-- 07_us_counties.sql
-- National county summary for the U.S. map: community water systems, people served,
-- share on wells, and health-based violations among small systems.
-- Needs the national EPA files in data/raw/ (run 06_national_tribal.sql first, which
-- builds us_systems and us_health_violations).
--
-- County comes from SDWA_GEOGRAPHIC_AREAS (AREA_TYPE_CODE 'CN'). ANSI_ENTITY_CODE is the
-- 3-digit county code, so the state has to come from the system ID: state-regulated IDs
-- start with the state's postal code. Tribal systems are tied to tribal areas, not counties,
-- so they are summarized by EPA region instead (06_national_tribal.sql).

CREATE OR REPLACE TABLE us_system_county AS
SELECT PWSID AS pwsid, MIN(ANSI_ENTITY_CODE) AS county3      -- one home county per system
FROM read_csv('data/raw/SDWA_GEOGRAPHIC_AREAS.csv', all_varchar = true)
WHERE AREA_TYPE_CODE = 'CN' AND ANSI_ENTITY_CODE IS NOT NULL
GROUP BY PWSID;

CREATE OR REPLACE TABLE us_state_fips (postal VARCHAR, fips VARCHAR);
INSERT INTO us_state_fips VALUES
 ('AL','01'),('AK','02'),('AZ','04'),('AR','05'),('CA','06'),('CO','08'),('CT','09'),('DE','10'),
 ('DC','11'),('FL','12'),('GA','13'),('HI','15'),('ID','16'),('IL','17'),('IN','18'),('IA','19'),
 ('KS','20'),('KY','21'),('LA','22'),('ME','23'),('MD','24'),('MA','25'),('MI','26'),('MN','27'),
 ('MS','28'),('MO','29'),('MT','30'),('NE','31'),('NV','32'),('NH','33'),('NJ','34'),('NM','35'),
 ('NY','36'),('NC','37'),('ND','38'),('OH','39'),('OK','40'),('OR','41'),('PA','42'),('RI','44'),
 ('SC','45'),('SD','46'),('TN','47'),('TX','48'),('UT','49'),('VT','50'),('VA','51'),('WA','53'),
 ('WV','54'),('WI','55'),('WY','56');

CREATE OR REPLACE TABLE us_state_systems AS
SELECT s.pwsid, f.postal AS state, f.fips || c.county3 AS fips, s.population_served,
       r.PRIMARY_SOURCE_CODE LIKE 'GW%' AS on_wells,
       EXISTS (SELECT 1 FROM us_health_violations v
               WHERE v.pwsid = s.pwsid AND v.began >= CURRENT_DATE - INTERVAL 5 YEAR) AS has_violation
FROM us_systems s
JOIN (SELECT PWSID, PRIMARY_SOURCE_CODE FROM read_csv('data/raw/SDWA_PUB_WATER_SYSTEMS.csv', all_varchar = true)
      QUALIFY ROW_NUMBER() OVER (PARTITION BY PWSID ORDER BY SUBMISSIONYEARQUARTER DESC) = 1) r ON r.PWSID = s.pwsid
JOIN us_state_fips f ON f.postal = LEFT(s.pwsid, 2)
JOIN us_system_county c ON c.pwsid = s.pwsid
WHERE s.primacy = 'State';

CREATE OR REPLACE TABLE us_county_pop AS
SELECT STATE || COUNTY AS fips, TRY_CAST(POPESTIMATE2025 AS INTEGER) AS population
FROM read_csv('data/raw/co-est2025-alldata.csv', header = true, all_varchar = true, encoding = 'latin-1')
WHERE SUMLEV = '050';

CREATE OR REPLACE TABLE us_county_summary AS
SELECT c.fips, ANY_VALUE(c.state) AS state,
       COUNT(*)                                                         AS systems,
       SUM(c.population_served)                                         AS people_served,
       SUM(CASE WHEN c.on_wells THEN c.population_served ELSE 0 END)
         / NULLIF(SUM(c.population_served), 0)                          AS share_on_wells,
       COUNT(*) FILTER (c.population_served < 500)                      AS small_systems,
       COUNT(*) FILTER (c.population_served < 500 AND c.has_violation)  AS small_with_violation,
       ANY_VALUE(p.population)                                          AS population
FROM us_state_systems c
LEFT JOIN us_county_pop p USING (fips)
GROUP BY c.fips;
