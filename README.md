# Mukera App

A simple one-page Python Flask web app, ready for deployment on Render and Git.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run locally:
   ```bash
   python app.py
   ```
3. Deploy to Render:
   - Add this repo to Render
   - Set build/run command to: `pip install -r requirements.txt && gunicorn app:app`

## Deployment files
- `Procfile`: For Render deployment (uses Gunicorn)
- `.gitignore`: Python and Flask ignores
- `requirements.txt`: Flask dependency
