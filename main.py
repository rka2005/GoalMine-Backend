from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS so React frontend can access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, use the actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class PlanningRequest(BaseModel):
    goal: str
    hoursPerDay: str
    timeSlot: Dict[str, str]

# Response model
class PlanResponse(BaseModel):
    plan: List[str]

@app.post("/generate-plan", response_model=PlanResponse)
def generate_plan(data: PlanningRequest):
    print("Received planning request:", data.dict())

    # Replace this dummy logic with your AI planner or LLM
    dummy_plan = [
        f"Day 1: Understand the basics of {data.goal}",
        f"Day 2: Deep dive into core concepts of {data.goal}",
        f"Day 3: Practice exercises for {data.goal}",
        f"Day 4: Project-based learning for {data.goal}",
    ]

    return {"plan": dummy_plan}
