import logging
import random
import string
import time
import uuid

import psycopg
import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import (  #Pydantic helps FastAPI understand and validate the incoming data.
    BaseModel,
    HttpUrl,
)

app = FastAPI() #creates the application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


#Pydantic check
class URLRequest(BaseModel):
    url: HttpUrl #A request to /shorten should contain a field called url, and it should be a valid url.

#Postgres Connection
conn = psycopg.connect(
    host = "localhost",
    port = 5432,
    dbname = "urlshortener",
    user = "postgres",
    password = "postgres"
)
cur = conn.cursor()


def record_click(code:str):
    try:
        cur.execute(
            '''
            Insert into clicks (short_code) values (%s)
            ''',
            (code,)
        )
        conn.commit()
    except psycopg.Error:
        conn.rollback()
        logger.exception("Failed to record click for %s",code)


#Redis Connection
r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

#rate-limit Dependency
Rate_Limit=10
WINDOW=60

def rate_limit(request:Request):
    ip=request.client.host
    key=f"rate_limit:{ip}"

    now = int(time.time()*1000)
    window_ms = WINDOW * 1000
    cutoff = now - window_ms

    try:
        while True:
            with r.pipeline() as pipe :
                try:
                    pipe.watch(key)
                    pipe.zremrangebyscore(key, "-inf", cutoff)
                    count=pipe.zcard(key)
                    if count>=Rate_Limit:
                        pipe.unwatch()
                        raise HTTPException(
                            status_code=429,
                            detail="Too many request"
                        )
                    pipe.multi()
                    pipe.zadd(
                        key,
                        {f"{now}:{uuid.uuid4().hex}": now}
                    )
                    pipe.expire(key,WINDOW)
                    pipe.execute()
                    break
                except redis.WatchError:
                    continue
    except HTTPException:
        raise
    except redis.RedisError:
        logger.exception("Redis rate limiter Failed")
        return


#Base62 Encoder code
characters = string.digits + string.ascii_lowercase + string.ascii_uppercase
def Base62Encode(number: int)->str:
    if number == 0:
        return "0"

    code= ""
    while number>0:
        remainder = number%62
        code = characters[remainder] + code
        number = number//62
    return code

#Code generater
def generate_code():
        code = random.randint(1,62**6-1)#will return a random code
        return Base62Encode(code)



#Shorten
@app.post("/shorten") #when someone sends a post request to this function runs the function defined below
def shorten(request: URLRequest,_: None = Depends(rate_limit)):  #My /shorten API expects a JSON object containing a url string.
    original_url = str(request.url)
    expires_at = None
    while True :
        short_code = generate_code()
        try:
            cur.execute(
               """
                INSERT INTO urls (short_code, original_url, expires_at)
                VALUES (%s, %s, %s)
                RETURNING short_code
                """,
                (short_code, original_url, expires_at)        
            )
            conn.commit()
            break
        except psycopg.errors.UniqueViolation:
            conn.rollback()
    return {
        "code": short_code,
        "short_url": f"http://localhost:8000/{short_code}"
    }


#Redirect
@app.get("/{code}")   #when someone visits code
def redirect(code: str):
    try:
        cached_url = r.get(code)
        
        if cached_url:
            logger.info("CACHE HIT: %s",code)
            record_click(code)

            return RedirectResponse(
            url=cached_url,
            status_code=302
            )
        
        logger.info("CACHE MISS: %s", code)

    except redis.RedisError as e:
        logger.error("REDIS ERROR while reading cache: %s", e)
    
    # Redis unavailable OR cache miss
    # Fall back to PostgreSQL
    cur.execute(
        "Select original_url from urls where short_code=%s  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",(code,)
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404,detail="URL not Found or expired")

    record_click(code)
    # 3. Store URL in Redis with 5-minute TTL
    original_url = row[0]
    try:
        r.set(code,original_url, ex=300)
        logger.info("CACHED: %s",code)

    except redis.RedisError as e:
        logger.error("Redis Error While Storing Cache: %s",e)

    return RedirectResponse(url=original_url,status_code=302)

# Top 10 most-clicked URLs
@app.get("/stats/top")
def get_top_urls():
    cur.execute(
        """
        SELECT
            u.short_code,
            u.original_url,
            COUNT(c.id) AS total_clicks
        FROM urls AS u
        JOIN clicks AS c
            ON u.short_code = c.short_code
        GROUP BY u.short_code, u.original_url
        ORDER BY total_clicks DESC, u.short_code ASC
        LIMIT 10
        """
    )

    rows = cur.fetchall()

    return [
        {
            "short_code": row[0],
            "original_url": row[1],
            "total_clicks": row[2]
        }
        for row in rows
    ]


# Daily click statistics for a short URL
@app.get("/stats/{code}")
def get_stats(code: str):
    # Check that the short URL exists
    cur.execute(
        "SELECT 1 FROM urls WHERE short_code = %s",
        (code,)
    )

    if cur.fetchone() is None:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found"
        )

    cur.execute(
        """
        SELECT
            clicked_at::date AS day,
            COUNT(*) AS clicks
        FROM clicks
        WHERE short_code = %s
        GROUP BY clicked_at::date
        ORDER BY day
        """,
        (code,)
    )

    rows = cur.fetchall()

    return [
        {
            "date": str(row[0]),
            "clicks": row[1]
        }
        for row in rows
    ]