from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fpdf import FPDF
import google.generativeai as genai
import os
import uuid
from datetime import datetime, timedelta

# Load API key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlanningRequest(BaseModel):
    goal: str
    hoursPerDay: str
    timeSlot: Dict[str, str]

@app.post("/generate-plan-pdf")
def generate_plan_pdf(data: PlanningRequest):
    prompt = (
        f"Create a detailed 5-day study plan in structured format for the goal: {data.goal}. "
        f"The user is available {data.hoursPerDay} hours per day between {data.timeSlot['start']} and {data.timeSlot['end']}. "
        f"Each day should include: Date, Day, Topics to Study, and Time Allotted. Format it as a neat list."
    )

    try:
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

        file_name = f"study_plan_{uuid.uuid4().hex[:8]}.pdf"
        file_path = f"./{file_name}"
        pdf.output(file_path)

        return FileResponse(path=file_path, media_type="application/pdf", filename="study_plan.pdf")

    except Exception as e:
        return {"error": str(e)}

@app.post("/generate-plan")
def generate_plan(data: PlanningRequest):
    prompt = (
        f"Create a detailed 5-day study plan in structured format for the goal: {data.goal}. "
        f"The user is available {data.hoursPerDay} hours per day between {data.timeSlot['start']} and {data.timeSlot['end']}. "
        f"Each day should include: Date, Day, Topics to Study, and Time Allotted. Return as a list of strings."
    )

    try:
        model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
        response = model.generate_content(prompt)
        plan_text = response.text.strip()

        # Split the response into a list of steps
        plan_list = [line.strip() for line in plan_text.split('\n') if line.strip()]

        return {"plan": plan_list}

    except Exception as e:
        return {"error": str(e)}
