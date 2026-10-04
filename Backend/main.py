from fastapi import FastAPI,HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel,HttpUrl  #Pydantic helps FastAPI understand and validate the incoming data.
import random
import string

app = FastAPI() #creates the application

#Pydantic check
class URLRequest(BaseModel):
    url: HttpUrl #A request to /shorten should contain a field called url, and it should be a valid url.


urls = {}  #temp database

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
counter =1
def generate_code():
    global counter
    while True:
        code = Base62Encode(counter)  #will return a random code
        counter=counter+1
        if code not in urls:
            return code



#Shorten
@app.post("/shorten") #when someone sends a post request to this function runs the function defined below
def shorten(request:URLRequest):  #My /shorten API expects a JSON object containing a url string.
    code = generate_code()
    urls[code] = str(request.url)
    return {
        "code":code,
        "short_url":f"http://localhost:8000/{code}"
    } #sends json back to server


#Redirect
@app.get("/{code}")   #when someone visits code
def redirect(code: str):
    if code not in urls:
        raise HTTPException(status_code=404,detail="URL not found")
    
    org_url = urls[code]

    return RedirectResponse(url=org_url,status_code=302)
    