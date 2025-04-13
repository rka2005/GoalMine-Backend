# GoalMineAI Backend

FastAPI backend service for GoalMineAI, providing AI-powered goal planning and PDF generation.

## Features

- 🤖 Integration with Google's Gemini 1.5 Flash
- 🔒 Firebase authentication
- 📄 PDF generation
- 🔄 CORS support
- 📝 Detailed logging

## Tech Stack

- FastAPI
- Google Gemini AI
- Firebase Admin SDK
- FPDF (PDF generation)
- Python 3.9+

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip
- Firebase Admin SDK credentials
- Google Gemini API key

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/GoalMineAI.git
cd GoalMine-Backend
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
```

5. Add your Firebase Admin SDK credentials:

- Download your Firebase Admin SDK JSON file
- Rename it to `firebase-adminsdk.json`
- Place it in the project root

6. Run the server:

```bash
uvicorn main:app --reload
```

## API Endpoints

### POST /generate-plan

Generate a study plan based on user input.

### POST /generate-plan-pdf

Generate and download a PDF version of the study plan.

### GET /health

Health check endpoint.

## Environment Variables

- `GEMINI_API_KEY`: Google Gemini API key
- Firebase credentials (via firebase-adminsdk.json)