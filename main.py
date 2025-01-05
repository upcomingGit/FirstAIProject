from openai import OpenAI
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

app = FastAPI()

load_dotenv()

# Set your OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#if not openai.api_key:
#    raise ValueError("OpenAI API Key not found. Please set it in the .env file")

# Template configuration (HTML templates)
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# This route serves the web form and handles the user input
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "message":None, "output": ""})

# This route processes the user input and displays the result
@app.post("/", response_class=HTMLResponse)
async def handle_form(request: Request, user_input: str = Form(...)):
    try:
        # Request to OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=1500,
            temperature=0.7,
            )
        output = response.choices[0].message.content.strip()
    except Exception as e:
        output = f"Error: {str(e)}"

    return templates.TemplateResponse("index.html", {"request": request, "user_input": user_input, "output": output})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
