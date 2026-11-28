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
print(con.sql("""SELECT COUNT(*) AS counties, SUM(systems) AS systems, SUM(people_served) AS people_served,
                 ROUND(100.0 * SUM(small_with_violation) / SUM(small_systems), 1) AS small_viol_pct
                 FROM us_county_summary"""))
print("Wrote output/us_county_summary.csv")
