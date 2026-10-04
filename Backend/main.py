from fastapi import FastAPI,HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel  #Pydantic helps FastAPI understand and validate the incoming data.
import random
import string

app = FastAPI() #creates the application

class URLRequest(BaseModel):
    url:str #A request to /shorten should contain a field called url, and it should be a string.

def generate_code():  #will return a random code
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters,k=6))     

urls = {}  #temp database

@app.post("/shorten") #when someone sends a post request to this function runs the function defined below

def shorten(request:URLRequest):  #My /shorten API expects a JSON object containing a url string.
    code = generate_code()
    urls[code] = request.url
    return {
        "code":code,
        "short_url":f"http://localhost:8000/{code}"
    } #sends json back to server


@app.get("/{code}")   #when someone visits code
def redirect(code: str):
    if code not in urls:
        raise HTTPException(status_code=404,detail="URL not found")
    
    org_url = urls[code]

    return RedirectResponse(url=org_url,status_code=302)
    