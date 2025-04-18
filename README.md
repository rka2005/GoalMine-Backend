# GoalMineAI Backend

A FastAPI service that generates study plans using Google's Gemini AI.

## Features

- AI-powered study plans
- PDF export
- Firebase authentication
- CORS enabled

## Setup

1. **Install Python 3.9+**

2. **Clone & Install**

```bash
git clone https://github.com/yourusername/GoalMineAI.git
cd GoalMine-Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure**

- Create `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
```

- Add `firebase-adminsdk.json` to root folder

4. **Run**

```bash
uvicorn main:app --reload
```

## API Endpoints

### POST /generate-plan

Creates a study plan

```json
{
  "goal": "Learn Python",
  "hoursPerDay": "2",
  "timeSlot": {
    "start": "09:00",
    "end": "11:00"
  }
}
```

### POST /generate-plan-pdf

Generates PDF version of the plan

### GET /health

Checks server status

## Requirements

- Python 3.9+
- Firebase credentials
- Gemini API key
