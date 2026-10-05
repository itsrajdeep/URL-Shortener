import psycopg

conn = psycopg.connect(
    host = "localhost",
    port = 5432,
    dbname = "urlshortener",
    user = "postgres",
    password = "postgres"
)

cur = conn.cursor()

cur.execute(
    """
    INSERT INTO urls (short_code, original_url)
    VALUES (%s, %s)
    """,
    ("abc123", "https://example.com")
)

conn.commit()

cur.execute(
    """
    SELECT id, short_code, original_url, created_at
    FROM urls
    """
)

rows = cur.fetchall()

for row in rows:
    print(row)


cur.close()
conn.close()
