"""Worker process entry point: ``python -m app.worker``."""

from app.worker.runner import run_worker_forever

if __name__ == "__main__":
    run_worker_forever()
