"""Run the SQL files in order and write results to output/."""
from pathlib import Path
import duckdb

con = duckdb.connect("water.duckdb")
HARDNESS_RAW = [Path("data/raw/wqp_ca_mg_results.csv"), Path("data/raw/wqp_stations.csv")]
have_hardness = all(p.exists() for p in HARDNESS_RAW)
for sql_file in sorted(Path("sql").glob("*.sql")):
    if sql_file.name == "05_hardness.sql" and not have_hardness:
        print("Skipping 05_hardness.sql (Water Quality Portal files not in data/raw)")
        continue
    print(f"Running {sql_file.name}")
    con.execute(sql_file.read_text())

print("\nMinnesota active community water systems by source:")
con.sql("""
    SELECT source_type,
           COUNT(*)               AS systems,
           SUM(population_served) AS people_served
    FROM mn_systems
    GROUP BY source_type
    ORDER BY people_served DESC
""").show()

print("Systems with no county, split by tribal (EPA-regulated) vs. state-regulated:")
con.sql("""
    SELECT is_tribal_epa_regulated, COUNT(*) AS systems, SUM(population_served) AS people
    FROM mn_systems_with_county
    WHERE county IS NULL
    GROUP BY ALL
""").show()

print("Health-based violations, last 5 years: tribal vs. state-regulated systems:")
con.sql("""
    SELECT is_tribal_epa_regulated,
           COUNT(*) AS systems,
           SUM(CASE WHEN health_violations_5yr > 0 THEN 1 ELSE 0 END) AS systems_with_violation,
           ROUND(100.0 * SUM(CASE WHEN health_violations_5yr > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_with_violation
    FROM mn_system_violations
    GROUP BY ALL
""").show()

print("Largest counties by people served:")
con.sql("""
    SELECT county, systems, people_served, ROUND(share_on_wells * 100) AS pct_on_wells
    FROM mn_county_summary
    ORDER BY people_served DESC
    LIMIT 10
""").show()

print("Health-based violations, last 5 years:")
con.sql("""
    SELECT source_type,
           COUNT(*)                                            AS systems,
           SUM(CASE WHEN health_violations_5yr > 0 THEN 1 ELSE 0 END) AS systems_with_violation,
           SUM(CASE WHEN health_violations_5yr > 0 THEN population_served ELSE 0 END) AS people_affected
    FROM mn_system_violations
    GROUP BY source_type
    ORDER BY systems DESC
""").show()

con.execute("COPY mn_systems_with_county TO 'output/mn_systems.csv' (HEADER)")
con.execute("COPY mn_county_summary TO 'output/mn_county_summary.csv' (HEADER)")
print("People not on a community water system (mostly private wells), by county:")
con.sql("""
    SELECT county, population_2025, community_served, est_not_on_community, pct_not_on_community
    FROM mn_private_wells
    ORDER BY est_not_on_community DESC
    LIMIT 10
""").show()
con.sql("""
    SELECT SUM(population_2025)      AS mn_population,
           SUM(est_not_on_community) AS est_not_on_community,
           ROUND(100.0 * SUM(est_not_on_community) / SUM(population_2025), 1) AS pct
    FROM mn_private_wells
""").show()

con.execute("COPY mn_system_violations TO 'output/mn_system_violations.csv' (HEADER)")
con.execute("COPY mn_private_wells TO 'output/mn_private_wells.csv' (HEADER)")
print("Wrote output/mn_systems.csv, mn_county_summary.csv, mn_system_violations.csv, mn_private_wells.csv")

if have_hardness:
    print("\nGroundwater hardness by county (mg/L as CaCO3), hardest first:")
    con.sql("""
        SELECT county, median_hardness_mg_l, hardness_class, wells
        FROM mn_hardness WHERE enough_wells
        ORDER BY median_hardness_mg_l DESC LIMIT 10
    """).show()
    con.sql("""
        SELECT COUNT(*) AS counties, SUM(enough_wells::INT) AS with_5plus_wells, SUM(wells) AS wells,
               ROUND(MEDIAN(median_hardness_mg_l)) AS median_county
        FROM mn_hardness
    """).show()
    con.execute("COPY (SELECT * FROM mn_hardness ORDER BY county) TO 'output/mn_hardness.csv' (HEADER)")
    print("Wrote output/mn_hardness.csv")
