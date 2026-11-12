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

con.execute("COPY mn_systems TO 'output/mn_systems.csv' (HEADER)")
print("Wrote output/mn_systems.csv")
