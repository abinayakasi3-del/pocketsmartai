# PocketSmart AI
FastAPI + Gemini budget & recommendation assistant (Home, Party, Jewelry planners).

## Run
    python -m venv venv && venv\Scripts\activate     (Mac/Linux: source venv/bin/activate)
    pip install -r requirements.txt
    copy .env.example .env      (then paste your Gemini API key from aistudio.google.com)
    uvicorn main:app --reload
Open http://127.0.0.1:8000, register, and try a planner. Without a key the app shows default suggestions.

## Structure
main.py (routes, auth, history) · gemini_utils.py (prompts, Gemini call, fallback) · templates/ (Jinja2 UI)
