import subprocess
import os
import sys
import time
import logging
import signal
import shutil
from scripts.init_db import init_db

# Configure logging for startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/startup.log")
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

def install_system_deps():
    """Auto-install missing system dependencies if in a Debian-based environment."""
    deps = {
        "ffmpeg": "ffmpeg",
        "redis-server": "redis-server",
        "magick": "imagemagick"
    }

    missing = []
    for cmd, package in deps.items():
        if shutil.which(cmd) is None:
            if cmd == "magick" and shutil.which("convert"):
                continue
            missing.append(package)

    if missing:
        logger.info(f"📦 Missing system dependencies found: {missing}")
        try:
            if shutil.which("apt-get"):
                logger.info("Attempting auto-installation via apt-get...")
                cmd_prefix = ["sudo"] if shutil.which("sudo") else []
                subprocess.run(cmd_prefix + ["apt-get", "update"], check=False)
                subprocess.run(cmd_prefix + ["apt-get", "install", "-y"] + missing, check=True)
                logger.info("✅ System dependencies installed.")
            else:
                logger.warning("⚠️ Non-Debian system detected. Please install missing deps manually.")
        except Exception as e:
            logger.error(f"❌ Failed to install dependencies: {e}")

def start_redis():
    """Ensure Redis is running, start if necessary."""
    try:
        subprocess.run(['redis-cli', 'ping'], capture_output=True, check=True)
        logger.info("✅ Redis is already running.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("📦 Attempting to start Redis server...")
        try:
            if shutil.which("redis-server"):
                subprocess.run(['redis-server', '--daemonize', 'yes'], check=True)
                time.sleep(2)
                subprocess.run(['redis-cli', 'ping'], capture_output=True, check=True)
                logger.info("✅ Redis started successfully.")
                return True
            else:
                logger.error("❌ redis-server not found in PATH.")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to start Redis: {e}")
            return False

def setup_env():
    """Auto-create .env from .env.example."""
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            logger.info("📝 Creating .env from .env.example...")
            shutil.copy(".env.example", ".env")
        else:
            logger.error("❌ Critical: .env.example missing.")
            return False
    return True

def main():
    # 0. Ensure directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("tmp", exist_ok=True)

    logger.info("🚀 Starting AI Video Editor System Setup...")

    # 1. System Dependencies
    install_system_deps()

    # 2. Environment Setup
    if not setup_env():
        sys.exit(1)

    # 3. Redis Startup
    if not start_redis():
        logger.error("❌ Redis is required but could not be started.")
        # Fallback logic could go here, but for now we exit
        sys.exit(1)

    # 4. Initialize DB
    if not os.path.exists("video_editor.db"):
        logger.info("📦 Initializing SQLite database...")
        init_db()

    # 5. Run Health Checks (Imported after env setup)
    from app.services.health_check import run_all_checks
    if not run_all_checks():
        logger.warning("⚠️ Health checks reported issues. System may be unstable.")

    # 6. Startup Recovery
    from app.services.recovery import recover_interrupted_jobs, cleanup_stale_artifacts
    logger.info("🔄 Running startup recovery and cleanup...")
    recover_interrupted_jobs()
    cleanup_stale_artifacts()

    # 7. Launch Processes
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    # Process 1: Worker
    # Detect RQ availability
    try:
        import rq
        logger.info("✅ RQ found. Starting worker...")
    except ImportError:
        logger.error("❌ RQ not found in python path.")
        sys.exit(1)

    logger.info("⚙️ Launching background worker...")
    worker_proc = subprocess.Popen(
        [sys.executable, "app/workers/rq_worker.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(worker_proc)

    # Process 2: Bot/API
    logger.info("🤖 Launching Bot and API...")
    bot_proc = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(bot_proc)

    logger.info("✨ ALL SYSTEMS INITIALIZED.")

    # 8. Monitor and Log process outputs
    # Using non-blocking reads or threads would be better for real-time,
    # but here we'll do a simple loop and periodic poll.

    try:
        import threading
        def log_stream(proc, name):
            for line in iter(proc.stdout.readline, ''):
                logger.info(f"[{name}] {line.strip()}")

        threading.Thread(target=log_stream, args=(worker_proc, "WORKER"), daemon=True).start()
        threading.Thread(target=log_stream, args=(bot_proc, "BOT/API"), daemon=True).start()

        while True:
            for p in processes:
                if p.poll() is not None:
                    logger.error(f"❌ Process {p.pid} exited with code {p.returncode}. Shutting down system...")
                    for other_p in processes:
                        if other_p.poll() is None:
                            other_p.terminate()
                    sys.exit(1)
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Stopping system...")

if __name__ == "__main__":
    main()
