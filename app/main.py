import uvicorn
import os

from app.api import app


def run() -> None:
    workers = int(os.getenv("WEB_CONCURRENCY", "1"))
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=workers)


if __name__ == "__main__":
    run()


