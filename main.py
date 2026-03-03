from fastapi import FastAPI
from fastapi.responses import JSONResponse
import requests
import os
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Your Ecobee API key from the developer portal
ECOBEE_CLIENT_ID = os.getenv("ECOBEE_CLIENT_ID")
if not ECOBEE_CLIENT_ID:
    raise RuntimeError("ECOBEE_CLIENT_ID environment variable is not set")
ECOBEE_AUTH_URL = "https://api.ecobee.com/authorize"
ECOBEE_TOKEN_URL = "https://api.ecobee.com/token"

# Store PIN info temporarily (in production, use a database)
pin_store = {}

@app.get("/ecobee/authorize")
def authorize(scope: str = "smartWrite"):
    """
    Step 1: Request a PIN from Ecobee
    """
    try:
        params = {
            "response_type": "ecobeePin",
            "client_id": ECOBEE_CLIENT_ID,
            "scope": scope
        }
        
        response = requests.get(ECOBEE_AUTH_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Store the authorization code for later use
        pin_store["code"] = data.get("code")
        pin_store["start_time"] = time.time()
        
        return {
            "pin": data.get("ecobeePin"),
            "expires_in_minutes": data.get("expires_in"),
            "message": f"Enter this PIN in your Ecobee app: {data.get('ecobeePin')}",
            "next_step": "Go to your Ecobee app/account and enter the PIN above"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/ecobee/status")
def check_authorization():
    """
    Step 2: Poll to see if user authorized and get the access token
    """
    try:
        if "code" not in pin_store:
            return {"error": "No authorization in progress. Call /ecobee/authorize first"}
        
        code = pin_store["code"]
        
        # Exchange the authorization code for an access token
        data = {
            "grant_type": "ecobeePin",
            "code": code,
            "client_id": ECOBEE_CLIENT_ID
        }
        
        response = requests.post(ECOBEE_TOKEN_URL, json=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        
        return {
            "success": True,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "message": "Authorization successful! You can now use the access token to call Ecobee API"
        }
    except requests.exceptions.HTTPError as e:
        # User hasn't authorized yet
        if e.response.status_code == 400:
            return {
                "authorized": False,
                "message": "User has not authorized yet. Check back in a few seconds.",
                "next_step": "Enter the PIN in your Ecobee app and try again"
            }
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def root():
    """Home page with instructions"""
    return {
        "message": "Ecobee Authorization Server",
        "steps": [
            "1. GET /ecobee/authorize?scope=smartWrite - Get a PIN",
            "2. Enter the PIN in your Ecobee app",
            "3. GET /ecobee/status - Check if authorized and get access token"
        ]
    }
