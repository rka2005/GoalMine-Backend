from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
from dotenv import load_dotenv
from fpdf import FPDF
import google.generativeai as genai
import os
import uuid
from datetime import datetime
from firebase_admin import credentials, initialize_app, auth
import firebase_admin
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables and configure Gemini
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=GEMINI_API_KEY)

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
    logger.error(f"Firebase initialization error: {str(e)}")
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
        logger.error(f"Token verification error: {str(e)}")
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
        f"Create a study plan for: '{data.goal}'\n\n"
        f"Available time: {data.hoursPerDay} hours per day\n"
        f"Time slot: {data.timeSlot['start']} to {data.timeSlot['end']}\n\n"
        f"Format the plan exactly as follows (example):\n"
        f"Day 1: April 14, 2025\n"
        f"Topics: [List specific topics]\n"
        f"Time Allotted: {data.timeSlot['start']} - {data.timeSlot['end']}\n\n"
        f"Day 2: April 15, 2025\n"
        f"Topics: [List specific topics]\n"
        f"Time Allotted: {data.timeSlot['start']} - {data.timeSlot['end']}\n\n"
    )

    try:
        model = genai.GenerativeModel(
            model_name="models/gemini-2.0-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        response = model.generate_content(prompt)
        if not response or not response.text:
            raise ValueError("Empty response from Gemini API")

        plan_list = [
            line.strip()
            for line in response.text.strip().split('\n')
            if line.strip() and not line.startswith('```')
        ]

        return {
            "plan": plan_list,
            "user_id": user_id,
            "user_email": user_email
        }

    except Exception as e:
        logger.error(f"Error generating plan: {str(e)}")
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
        # Generate plan with structured format
        model = genai.GenerativeModel(
            model_name="models/gemini-2.0-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )

        # Use the same prompt format as generate-plan for consistency
        prompt = (
            f"Create a study plan for: '{data.goal}'\n\n"
            f"Available time: {data.hoursPerDay} hours per day\n"
            f"Time slot: {data.timeSlot['start']} to {data.timeSlot['end']}\n\n"
            f"Format the plan exactly as follows:\n"
            f"Day 1: April 14, 2025\n"
            f"Topics: [List specific topics]\n"
            f"Time Allotted: {data.timeSlot['start']} - {data.timeSlot['end']}\n\n"
        )

        response = model.generate_content(prompt)
        if not response or not response.text:
            raise ValueError("Empty response from Gemini API")

        # Create PDF
        pdf = FPDF()
        pdf.add_page()

        # Set font and styling
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Study Plan", ln=True, align="C")
        pdf.ln(5)

        # Add goal section
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Goal:", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, data.goal)
        pdf.ln(5)

        # Add availability section
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Availability:", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, f"Hours per day: {data.hoursPerDay}")
        pdf.multi_cell(
            0, 10, f"Time slot: {data.timeSlot['start']} - {data.timeSlot['end']}")
        pdf.ln(10)

        # Add plan content
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Daily Plan:", ln=True)
        pdf.ln(5)

        # Format and add the plan content
        plan_content = response.text.strip().split('\n')
        pdf.set_font("Arial", "", 12)
        for line in plan_content:
            if line.startswith('Day'):
                pdf.set_font("Arial", "B", 12)
                pdf.ln(5)
            pdf.multi_cell(0, 10, line)
            pdf.set_font("Arial", "", 12)

        # Save PDF
        os.makedirs("./tmp", exist_ok=True)
        file_name = f"study_plan_{user_id}_{uuid.uuid4().hex[:8]}.pdf"
        file_path = f"./tmp/{file_name}"
        pdf.output(file_path)

        # Clean up old files (optional)
        for f in os.listdir("./tmp"):
            if f.startswith(f"study_plan_{user_id}_"):
                file_age = datetime.now() - \
                    datetime.fromtimestamp(os.path.getctime(f"./tmp/{f}"))
                if file_age.days > 1:  # Remove files older than 1 day
                    os.remove(f"./tmp/{f}")

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=file_name,
            headers={
                "Content-Disposition": f"attachment; filename={file_name}"
            }
        )

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating PDF: {str(e)}"
        )


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
