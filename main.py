from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
from dotenv import load_dotenv
from fpdf import FPDF
import google.generativeai as genai
import os
import uuid
from datetime import datetime, timedelta
from firebase_admin import credentials, initialize_app, auth
import firebase_admin
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pytz
import re
import json
import base64

# Add these new imports at the top of the file
from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    REDIRECT_URI,
    SCOPES
)

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:  # Check if already initialized
        cred = credentials.Certificate(
            "./firebase-adminsdk.json"
        )
        firebase_admin.initialize_app(cred, {
            'projectId': 'goalmine-bcc41',
        })
except Exception as e:
    print(f"Firebase initialization error: {str(e)}")
    raise

app = FastAPI()

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Update with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
    expose_headers=["*"]
)

# Security bearer token setup
security = HTTPBearer()

# Firebase token verification function
async def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        # Add clock tolerance for time sync issues
        decoded_token = auth.verify_id_token(
            credentials.credentials,
            check_revoked=True,
            clock_skew_seconds=60  # Add 60 seconds tolerance
        )
        return decoded_token
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired. Please sign in again.",
        )
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked. Please sign in again.",
        )
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

class PlanningRequest(BaseModel):
    goal: str
    hoursPerDay: str
    timeSlot: Dict[str, str]

# Modified generate-plan endpoint with Firebase auth
@app.post("/generate-plan")
async def generate_plan(
    data: PlanningRequest,
    token: dict = Depends(verify_firebase_token)
):
    user_id = token['uid']
    user_email = token.get('email', 'No email')

    print(f"Request from user: {user_email} (ID: {user_id})")

    prompt = (
        f"Based on the goal: '{data.goal}'\n\n"
        f"Create a study plan that fits within these constraints:\n"
        f"- Daily available time: {data.hoursPerDay} hours\n"
        f"- Time slot: {data.timeSlot['start']} to {data.timeSlot['end']}\n\n"
        f"Format each day exactly as follows:\n"
        f"Day [number]: [current date + day number]\n"
        f"Topics: [specific topics related to {data.goal}]\n"
        f"Time Allotted: [time slots within {data.timeSlot['start']} - {data.timeSlot['end']}]"
    )

    try:
        model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
        response = model.generate_content(prompt)
        plan_text = response.text.strip()

        plan_list = [
            line.strip()
            for line in plan_text.split('\n')
            if line.strip() and not line.startswith('```')
        ]

        return {
            "plan": plan_list,
            "user_id": user_id,
            "user_email": user_email
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating plan: {str(e)}"
        )

# Modified generate-plan-pdf endpoint with Firebase auth
@app.post("/generate-plan-pdf")
async def generate_plan_pdf(
    data: PlanningRequest,
    token: dict = Depends(verify_firebase_token)
):
    user_id = token['uid']

    try:
        prompt = (
            f"Create a detailed 5-day study plan in structured format for the goal: {data.goal}. "
            f"The user is available {data.hoursPerDay} hours per day between {data.timeSlot['start']} and {data.timeSlot['end']}. "
            f"Each day should include: Date, Day, Topics to Study, and Time Allotted. Format it as a neat list."
        )

        model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
        response = model.generate_content(prompt)
        plan_text = response.text.strip()

        # Parse content into PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(200, 10, txt="Structured 5-Day Study Plan", ln=True, align="C")

        # Add metadata
        pdf.ln(5)
        pdf.cell(200, 10, txt=f"Goal: {data.goal}", ln=True)
        pdf.cell(200, 10, txt=f"Daily Study Time: {data.hoursPerDay} hrs", ln=True)
        pdf.cell(200, 10, txt=f"Time Slot: {data.timeSlot['start']} - {data.timeSlot['end']}", ln=True)
        pdf.ln(10)

        for line in plan_text.split('\n'):
            line = line.strip()
            if line:
                pdf.multi_cell(0, 10, line)

        file_name = f"study_plan_{user_id}_{uuid.uuid4().hex[:8]}.pdf"
        file_path = f"./tmp/{file_name}"

        # Ensure tmp directory exists
        os.makedirs("./tmp", exist_ok=True)

        pdf.output(file_path)

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=file_name
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating PDF: {str(e)}"
        )

# Add new endpoint for calendar sync
@app.post("/sync-calendar")
async def sync_calendar(request: Request, token: dict = Depends(verify_firebase_token)):
    try:
        data = await request.json()
        plan = data.get('plan', [])
        calendar_credentials = data.get('calendar_credentials')

        if not plan or not calendar_credentials:
            raise HTTPException(status_code=400, detail="Missing required data")

        # Create credentials object from the received credentials
        credentials = Credentials(
            token=calendar_credentials['token'],
            refresh_token=calendar_credentials['refresh_token'],
            token_uri=calendar_credentials['token_uri'],
            client_id=calendar_credentials['client_id'],
            client_secret=calendar_credentials['client_secret'],
            scopes=calendar_credentials['scopes']
        )

        # Initialize Google Calendar API
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Create calendar events from the plan
        events = []
        for day in plan:
            # Parse day info using regex
            day_match = re.search(r'Day (\d+): (.+)', day)
            topics_match = re.search(r'Topics: (.+?)(?=Time Allotted:)', day)
            time_match = re.search(r'Time Allotted: (.+)', day)

            if day_match and topics_match and time_match:
                day_num = int(day_match.group(1))
                topics = topics_match.group(1).strip()
                time_slots = time_match.group(1).strip()

                # Calculate event date
                event_date = datetime.now() + timedelta(days=day_num-1)

                # Parse time slots
                for time_slot in time_slots.split(';'):
                    if '-' in time_slot:
                        start_time, end_time = map(str.strip, time_slot.split('-'))

                        # Create datetime objects
                        start_dt = datetime.strptime(
                            f"{event_date.date()} {start_time}",
                            "%Y-%m-%d %H:%M"
                        )
                        end_dt = datetime.strptime(
                            f"{event_date.date()} {end_time}",
                            "%Y-%m-%d %H:%M"
                        )

                        event = {
                            'summary': f'Study Session: {topics}',
                            'description': f'Study plan for Day {day_num}\n\nTopics: {topics}',
                            'start': {
                                'dateTime': start_dt.isoformat(),
                                'timeZone': 'UTC',
                            },
                            'end': {
                                'dateTime': end_dt.isoformat(),
                                'timeZone': 'UTC',
                            },
                            'reminders': {
                                'useDefault': False,
                                'overrides': [
                                    {'method': 'email', 'minutes': 24 * 60},
                                    {'method': 'popup', 'minutes': 30},
                                ],
                            },
                        }
                        events.append(event)

        # Create Google Calendar service
        credentials = Credentials.from_authorized_user_info(
            info={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": token.get("refresh_token"),
            },
            scopes=SCOPES
        )

        calendar_service = build('calendar', 'v3', credentials=credentials)

        # Add events to calendar
        created_events = []
        for event in events:
            try:
                created_event = calendar_service.events().insert(
                    calendarId='primary',
                    body=event
                ).execute()
                created_events.append(created_event)
            except Exception as e:
                print(f"Error creating event: {e}")
                continue

        return {
            "status": "success",
            "message": f"Successfully created {len(created_events)} calendar events",
            "events": created_events
        }

    except Exception as e:
        print(f"Calendar sync error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync calendar: {str(e)}"
        )

# Update the Google auth endpoint
@app.get("/auth/google")
async def google_auth(state: str = None):
    if not state:
        raise HTTPException(status_code=400, detail="State parameter is required")

    try:
        # Create OAuth2 flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Include the state parameter
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent screen to get refresh token
        )

        return HTMLResponse(content=f"""
            <script>
                window.location.href = "{authorization_url}";
            </script>
        """)
    except Exception as e:
        print(f"Auth error: {str(e)}")
        return HTMLResponse(content=f"""
            <script>
                window.opener.postMessage(
                    {{ type: 'calendar_auth_error', error: 'Failed to initialize authentication' }},
                    'http://localhost:5173'
                );
                window.close();
            </script>
        """)

# Update the callback endpoint
@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None, state: str = None):
    if error:
        return HTMLResponse(content=f"""
            <script>
                window.opener.postMessage(
                    {{ type: 'calendar_auth_error', error: '{error}' }},
                    'http://localhost:5173'
                );
                window.close();
            </script>
        """)

    try:
        # Decode state parameter
        state_data = json.loads(base64.b64decode(state).decode('utf-8'))

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Exchange code for credentials
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Verify the Firebase token from state
        try:
            decoded_token = auth.verify_id_token(state_data['token'])
            if decoded_token['uid'] != state_data['userId']:
                raise ValueError("User ID mismatch")
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid authentication")

        return HTMLResponse(content=f"""
            <script>
                window.opener.postMessage(
                    {{
                        type: 'calendar_auth_success',
                        credentials: {{
                            token: '{credentials.token}',
                            refresh_token: '{credentials.refresh_token}',
                            token_uri: '{credentials.token_uri}',
                            client_id: '{credentials.client_id}',
                            client_secret: '{credentials.client_secret}',
                            scopes: {credentials.scopes}
                        }}
                    }},
                    'http://localhost:5173'
                );
                window.close();
            </script>
        """)

    except Exception as e:
        print(f"Callback error: {str(e)}")
        return HTMLResponse(content=f"""
            <script>
                window.opener.postMessage(
                    {{ type: 'calendar_auth_error', error: 'Authentication failed: {str(e)}' }},
                    'http://localhost:5173'
                );
                window.close();
            </script>
        """)

def parse_day_info(day_text):
    try:
        # Add your parsing logic here to extract:
        # - day number
        # - topics
        # - start time
        # - end time
        # from the day_text

        # Return structured data
        return {
            'day_number': day_number,
            'topics': topics,
            'start_time': start_time,
            'end_time': end_time
        }
    except Exception as e:
        print(f"Error parsing day info: {e}")
        return None

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
