"""
Main entry point for Vercel deployment.

This file exports the FastAPI app instance for Vercel's automatic deployment.
Vercel looks for an 'app' variable in files like main.py, app.py, or index.py.
"""

from src.api.api import app

# Export the app for Vercel
__all__ = ["app"]
