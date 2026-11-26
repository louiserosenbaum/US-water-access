-- 05_hardness.sql
-- Groundwater hardness by county, from calcium and magnesium measured in well water.
--
-- Source: Water Quality Portal (waterqualitydata.us), Minnesota wells, samples since 2010.
--   data/raw/wqp_ca_mg_results.csv  (Result, narrow profile: characteristicName = Calcium, Magnesium)
--   data/raw/wqp_stations.csv       (Station: where each well is, incl. county FIPS)
-- Most readings come from the Minnesota Pollution Control Agency and DNR ambient groundwater programs.
--
-- Why calculate it: few samples report "hardness" directly, but almost every sample reports calcium
-- and magnesium. Hardness (mg/L as CaCO3) = 2.497 x calcium + 4.118 x magnesium (Standard Methods 2340 B).
--
-- Steps: keep dissolved results in mg/L that were actually detected, pair calcium with magnesium from
-- the same sample, take each well's median, then each county's median across wells.
-- Counties with fewer than 5 wells are flagged rather than colored, since a handful of wells can't
-- stand for a whole county.

CREATE OR REPLACE TABLE wqp_ca_mg AS
SELECT
    MonitoringLocationIdentifier                     AS well_id,
    ActivityIdentifier                               AS sample_id,
    TRY_CAST(ActivityStartDate AS DATE)              AS sampled,
    CharacteristicName                               AS characteristic,
    TRY_CAST(ResultMeasureValue AS DOUBLE)           AS mg_l
FROM read_csv('data/raw/wqp_ca_mg_results.csv', header = true, all_varchar = true)
WHERE CharacteristicName IN ('Calcium', 'Magnesium')
  AND LOWER("ResultMeasure/MeasureUnitCode") = 'mg/l'
  AND ResultSampleFractionText IN ('Dissolved', 'Filtered, lab')
  AND ResultDetectionConditionText IS NULL           -- drop non-detects
  AND TRY_CAST(ResultMeasureValue AS DOUBLE) IS NOT NULL;

-- one hardness value per sample that has both calcium and magnesium
CREATE OR REPLACE TABLE wqp_sample_hardness AS
SELECT
    well_id,
    sample_id,
    MIN(sampled)                                                     AS sampled,
    2.497 * AVG(mg_l) FILTER (WHERE characteristic = 'Calcium')
  + 4.118 * AVG(mg_l) FILTER (WHERE characteristic = 'Magnesium')   AS hardness_mg_l
FROM wqp_ca_mg
GROUP BY well_id, sample_id
HAVING COUNT(*) FILTER (WHERE characteristic = 'Calcium') > 0
   AND COUNT(*) FILTER (WHERE characteristic = 'Magnesium') > 0;

CREATE OR REPLACE TABLE wqp_wells AS
SELECT
    MonitoringLocationIdentifier             AS well_id,
    LPAD(CountyCode, 3, '0')                 AS county_fips,
    TRY_CAST(LatitudeMeasure AS DOUBLE)      AS lat,
    TRY_CAST(LongitudeMeasure AS DOUBLE)     AS lon
FROM read_csv('data/raw/wqp_stations.csv', header = true, all_varchar = true)
WHERE StateCode = '27';

CREATE OR REPLACE TABLE well_hardness AS
SELECT
    h.well_id,
    w.county_fips,
    MEDIAN(h.hardness_mg_l)  AS median_hardness_mg_l,
    COUNT(*)                 AS samples
FROM wqp_sample_hardness AS h
JOIN wqp_wells AS w USING (well_id)
GROUP BY h.well_id, w.county_fips;

CREATE OR REPLACE TABLE mn_hardness AS
SELECT
    p.county,
    ROUND(MEDIAN(wh.median_hardness_mg_l), 0)  AS median_hardness_mg_l,
    CASE
        WHEN MEDIAN(wh.median_hardness_mg_l) <= 60  THEN 'soft'
        WHEN MEDIAN(wh.median_hardness_mg_l) <= 120 THEN 'moderately hard'
        WHEN MEDIAN(wh.median_hardness_mg_l) <= 180 THEN 'hard'
        ELSE 'very hard'
    END                                         AS hardness_class,
    COUNT(*)                                    AS wells,
    SUM(wh.samples)                             AS samples,
    COUNT(*) >= 5                               AS enough_wells
FROM well_hardness AS wh
JOIN mn_county_population AS p ON p.county_fips = wh.county_fips
GROUP BY p.county;
