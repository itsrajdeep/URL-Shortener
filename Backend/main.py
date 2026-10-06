import random
import string

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import (  #Pydantic helps FastAPI understand and validate the incoming data.
    BaseModel,
    HttpUrl,
)

app = FastAPI() #creates the application

#Pydantic check
class URLRequest(BaseModel):
    url: HttpUrl #A request to /shorten should contain a field called url, and it should be a valid url.

conn = psycopg.connect(
    host = "localhost",
    port = 5432,
    dbname = "urlshortener",
    user = "postgres",
    password = "postgres"
)
cur = conn.cursor()

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
def shorten(request: URLRequest):  #My /shorten API expects a JSON object containing a url string.
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
    cur.execute(
        "Select original_url from urls where short_code=%s  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",(code,)
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404,detail="URL not Found or expired")

    return RedirectResponse(url=row[0],status_code=302)

