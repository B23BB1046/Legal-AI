import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router




app = FastAPI(

    title="Supreme Courtroom Assistant",

    description="AI-powered Indian legal research assistant",

    version="1.0"

)




app.add_middleware(

    CORSMiddleware,

    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:8501,http://localhost:8501",
    ).split(","),

    allow_credentials=False,

    allow_methods=["*"],

    allow_headers=["*"]

)




app.include_router(router)



# Home Page


@app.get("/")
def home():

    return {

        "message": "Welcome to Supreme Courtroom Assistant"

    }