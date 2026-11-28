"""Build the national tables (steps 06 and 07) and write the small CSVs the U.S. map uses.

The national violations file is about 4 GB. If data/raw/ holds the small extracts
health_viol.parquet and geo_counties.parquet, they are used instead of the big CSVs
(same rows, already filtered), which turns a several-minute run into seconds.
"""
from pathlib import Path

import duckdb

RAW = Path("data/raw")
PWS = "data/raw/SDWA_PUB_WATER_SYSTEMS.csv"
if not Path(PWS).exists() and (RAW / "SDWA_PUB_WATER_SYSTEMS_national.csv").exists():
    PWS = "data/raw/SDWA_PUB_WATER_SYSTEMS_national.csv"

VIOL_CSV = """SELECT DISTINCT PWSID AS pwsid, VIOLATION_ID AS violation_id,
       TRY_STRPTIME(NON_COMPL_PER_BEGIN_DATE, '%m/%d/%Y')::DATE AS began
FROM read_csv('data/raw/SDWA_VIOLATIONS_ENFORCEMENT.csv', all_varchar = true)
WHERE IS_HEALTH_BASED_IND = 'Y';"""
GEO_CSV = """SELECT PWSID AS pwsid, MIN(ANSI_ENTITY_CODE) AS county3      -- one home county per system
FROM read_csv('data/raw/SDWA_GEOGRAPHIC_AREAS.csv', all_varchar = true)
WHERE AREA_TYPE_CODE = 'CN' AND ANSI_ENTITY_CODE IS NOT NULL
GROUP BY PWSID;"""


def load(name):
    sql = Path("sql", name).read_text().replace("data/raw/SDWA_PUB_WATER_SYSTEMS.csv", PWS)
    if (RAW / "health_viol.parquet").exists():
        sql = sql.replace(VIOL_CSV, "SELECT pwsid, violation_id, began FROM 'data/raw/health_viol.parquet';")
    if (RAW / "geo_counties.parquet").exists():
        sql = sql.replace(GEO_CSV, """SELECT pwsid, MIN(ansi) AS county3 FROM 'data/raw/geo_counties.parquet'
WHERE area_type = 'CN' AND ansi IS NOT NULL GROUP BY pwsid;""")
    return sql


con = duckdb.connect()
for f in ["06_national_tribal.sql", "07_us_counties.sql"]:
    print("Running", f)
    con.execute(load(f))

con.execute("COPY (SELECT * FROM us_county_summary ORDER BY fips) TO 'output/us_county_summary.csv' (HEADER)")
con.execute("COPY (SELECT * FROM us_tribal_by_region) TO 'output/us_tribal_by_region_counts.csv' (HEADER)")
# State-by-state small-system violation rates and a size/source breakdown, for the "What stands out" section
con.execute("""COPY (
  SELECT state, COUNT(*) FILTER (population_served < 500) AS small_systems,
         COUNT(*) FILTER (population_served < 500 AND has_violation) AS small_with_violation,
         COUNT(*) AS systems, SUM(population_served) AS people_served,
         SUM(CASE WHEN on_wells THEN population_served ELSE 0 END) / NULLIF(SUM(population_served), 0) AS share_on_wells
  FROM us_state_systems GROUP BY state ORDER BY state) TO 'output/us_state_summary.csv' (HEADER)""")
con.execute("""COPY (
  SELECT CASE WHEN population_served < 100 THEN '1 under 100'
              WHEN population_served < 500 THEN '2 100-499'
              WHEN population_served < 3300 THEN '3 500-3,299'
              WHEN population_served < 10000 THEN '4 3,300-9,999'
              ELSE '5 10,000+' END AS size_band,
         CASE WHEN on_wells THEN 'wells' ELSE 'surface' END AS source,
         COUNT(*) AS systems, COUNT(*) FILTER (has_violation) AS with_violation
  FROM us_state_systems GROUP BY ALL ORDER BY 1, 2) TO 'output/us_size_source.csv' (HEADER)""")
print(con.sql("""SELECT COUNT(*) AS counties, SUM(systems) AS systems, SUM(people_served) AS people_served,
                 ROUND(100.0 * SUM(small_with_violation) / SUM(small_systems), 1) AS small_viol_pct
                 FROM us_county_summary"""))
print("Wrote output/us_county_summary.csv")
