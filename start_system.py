import subprocess
import os
import sys
import time
import logging
import signal
from app.services.health_check import run_all_checks
from app.services.recovery import recover_interrupted_jobs, cleanup_stale_artifacts
from scripts.init_db import init_db

# Configure logging for startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("startup.log")
    ]
)
logger = logging.getLogger("startup")

processes = []

def signal_handler(sig, frame):
    logger.info("Termination signal received. Shutting down all processes...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating process {p.pid}: {e}")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def start_redis():
    """Ensure Redis is running, start if necessary."""
    try:
        subprocess.run(['redis-cli', 'ping'], capture_output=True, check=True)
        logger.info("✅ Redis is already running.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("📦 Starting Redis server...")
        try:
            # We use daemonize yes to let it run in background managed by the OS/Codespace
            subprocess.run(['redis-server', '--daemonize', 'yes'], check=True)
            time.sleep(2)
            subprocess.run(['redis-cli', 'ping'], capture_output=True, check=True)
            logger.info("✅ Redis started successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to start Redis: {e}")
            return False
    return True

def main():
    logger.info("🚀 Initializing AI Video Editor Bot System...")

    # 1. Environment Check
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            logger.warning("⚠️ .env missing. Copying from .env.example...")
            import shutil
            shutil.copy(".env.example", ".env")
        else:
            logger.error("❌ .env and .env.example missing. Cannot proceed.")
            sys.exit(1)

    # 2. Start Redis
    if not start_redis():
        logger.error("❌ Critical: Redis is required for job queuing.")
        sys.exit(1)

    # 3. Initialize DB
    if not os.path.exists("video_editor.db"):
        logger.info("📦 Initializing database...")
        init_db()

    # 4. Run Health Checks
    # This checks FFmpeg, DB, Redis, Env
    if not run_all_checks():
        logger.error("❌ Health checks failed. System is not production-ready.")
        sys.exit(1)

    # 5. Recovery
    # Fail abandoned jobs and clean stale artifacts
    logger.info("🔄 Running recovery procedures...")
    recover_interrupted_jobs()
    cleanup_stale_artifacts()

    # 6. Start RQ Worker
    logger.info("⚙️ Starting background worker (RQ)...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    worker_proc = subprocess.Popen(
        [sys.executable, "-m", "rq", "worker", "video_processing"],
        env=env
    )
    processes.append(worker_proc)

    # 7. Start Bot & API (app.main)
    logger.info("🤖 Starting Bot and API (FastAPI)...")
    bot_proc = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        env=env
    )
    processes.append(bot_proc)

    logger.info("✨ System is fully operational. Monitoring processes...")

    # 8. Monitor Processes
    try:
        while True:
            for p in processes:
                exit_code = p.poll()
                if exit_code is not None:
                    logger.error(f"❌ Process {p.args} terminated unexpectedly with code {exit_code}")
                    # Fail-fast: shut down everything if a core component dies
                    for other_p in processes:
                        if other_p.poll() is None:
                            other_p.terminate()
                    sys.exit(1)
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping system...")

if __name__ == "__main__":
    main()
