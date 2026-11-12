"""Run the SQL files in order and write results to output/."""
from pathlib import Path
import duckdb

con = duckdb.connect("water.duckdb")
for sql_file in sorted(Path("sql").glob("*.sql")):
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

print("Systems with no county match (should be close to 0):")
con.sql("SELECT COUNT(*) AS no_county FROM mn_systems_with_county WHERE county IS NULL").show()

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
con.execute("COPY mn_system_violations TO 'output/mn_system_violations.csv' (HEADER)")
print("Wrote output/mn_systems.csv, mn_county_summary.csv, mn_system_violations.csv")
