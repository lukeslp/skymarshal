# Skymarshal

Skymarshal is a tool for [brief description]. This repository contains both the Python backend (CLI and Flask APIs) and the React frontend.

## Structure
- `backend/`: Python code for CLI, Flask APIs, and legacy web UIs.
- `frontend/`: React + TypeScript frontend built with Vite.
- `scripts/`: Utility scripts for development and deployment.

## Development Setup
### Backend
1. Install Python dependencies: `pip install -e backend/`
2. Run Flask server: `python backend/run.py`

### Frontend
1. Install Node.js dependencies: `cd frontend && npm install`
2. Run Vite dev server: `npm run dev` (proxies API requests to Flask)

## Deployment
[Instructions for building frontend and serving via Flask/Caddy]

## Related Projects
Skymarshal is part of the larger bluesky collection. See [link to bluesky documentation or repo] for related apps.
