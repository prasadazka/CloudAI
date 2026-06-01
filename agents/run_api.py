"""
Local dev runner. Starts the FastAPI app on http://localhost:8000.
    python run_api.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn


def main():
    uvicorn.run(
        "agents.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
