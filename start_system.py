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
    """Auto-create .env from .env.example and validate token with duplicate protection."""
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            logger.info("📝 AUTO-FIX APPLIED: Creating .env from .env.example...")
            shutil.copy(".env.example", ".env")
        else:
            logger.error("❌ Critical: .env.example missing.")
            return False

    # Read and sanitize .env to prevent duplicates
    env_vars = {}
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                env_vars[key.strip()] = val.strip()

    # Rewrite .env without duplicates
    with open(".env", "w") as f:
        for key, val in env_vars.items():
            f.write(f"{key}={val}\n")

    # Strict Token Validation
    token = env_vars.get("BOT_TOKEN", "").strip()
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN" or ":" not in token or len(token) < 30:
        logger.warning(f"⚠️ WARNING: BOT_TOKEN is missing or invalid ('{token}')")
        logger.warning("👉 Bot process will be skipped.")
        return "SKIP_BOT"

    return True

def start_worker(env):
    """Start and monitor RQ worker."""
    logger.info("⚙️ Launching background worker...")

    # Standard entrypoint via app.workers.rq_worker
    rq_cmd_args = [sys.executable, "app/workers/rq_worker.py"]

    try:
        worker_proc = subprocess.Popen(
            rq_cmd_args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        logger.info(f"Worker started with PID {worker_proc.pid} via {rq_cmd_args}")
        return worker_proc
    except Exception as e:
        logger.error(f"❌ Failed to launch worker: {e}")
        return None

def main():
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
        sys.exit(1)

    # 4. Initialize DB
    if not os.path.exists("video_editor.db"):
        logger.info("📦 Initializing SQLite database...")
        init_db()

    # 5. Run Health Checks
    from app.services.health_check import check_redis, check_db, check_ffmpeg, check_imagemagick

    print("\n" + "="*40)
    print("🚀 AI VIDEO EDITOR SYSTEM BOOT")
    print("="*40)

    results = {
        "Redis": check_redis(),
        "Database": check_db(),
        "FFmpeg": check_ffmpeg(),
        "ImageMagick": check_imagemagick(),
        "Env (.env)": True # Handled in setup_env
    }

    all_pass = True
    for component, status in results.items():
        dot_fill = "." * (20 - len(component))
        status_str = "OK" if status else "FAIL"
        if not status: all_pass = False
        print(f"[BOOT] {component} {dot_fill} {status_str}")

    if not all_pass:
        logger.error("❌ Critical components failed to boot. Aborting.")
        sys.exit(1)

    # 6. Startup Recovery
    from app.services.recovery import recover_interrupted_jobs, cleanup_stale_artifacts
    logger.info("🔄 Running startup recovery and cleanup...")
    recover_interrupted_jobs()
    cleanup_stale_artifacts()

    # 7. Launch Processes
    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    worker_proc = start_worker(env)
    if not worker_proc:
        logger.error("❌ Failed to start worker.")
        # Worker is critical
        sys.exit(1)
    processes.append(worker_proc)

    bot_status = setup_env()
    if bot_status != "SKIP_BOT":
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
    else:
        # If no bot token, we still want the API if possible,
        # but app.main usually starts both.
        logger.warning("🚫 Bot startup skipped due to invalid token.")
        # Create a dummy bot_proc for the monitoring loop if needed,
        # but let's just adjust the loop.
        bot_proc = None

    # 8. Verify Processes
    time.sleep(5)
    worker_status = "OK" if worker_proc and worker_proc.poll() is None else "FAIL"
    bot_status = "OK" if bot_proc and bot_proc.poll() is None else "FAIL"

    if not bot_proc: bot_status = "SKIPPED"

    print(f"[BOOT] Worker .............. {worker_status}")
    print(f"[BOOT] Bot ................. {bot_status}")
    print(f"[BOOT] API ................. {bot_status}")
    print("="*40)

    if worker_status == "FAIL" or bot_status == "FAIL":
        logger.error("❌ Processes failed to start after initialization.")
        sys.exit(1)

    logger.info("✨ ALL SYSTEMS INITIALIZED.")

    # 9. Monitor and Log
    import threading
    def log_stream(proc, name):
        for line in iter(proc.stdout.readline, ''):
            logger.info(f"[{name}] {line.strip()}")

    if worker_proc:
        threading.Thread(target=log_stream, args=(worker_proc, "WORKER"), daemon=True).start()
    if bot_proc:
        threading.Thread(target=log_stream, args=(bot_proc, "BOT/API"), daemon=True).start()

    worker_restarts = 0
    while True:
        # Check Worker
        if worker_proc and worker_proc.poll() is not None:
            logger.error(f"❌ Worker process {worker_proc.pid} exited with code {worker_proc.returncode}")
            if worker_restarts < 3:
                worker_restarts += 1
                logger.info(f"🔄 Restarting worker (Attempt {worker_restarts}/3)...")
                if worker_proc in processes:
                    processes.remove(worker_proc)
                worker_proc = start_worker(env)
                if worker_proc:
                    processes.append(worker_proc)
                    threading.Thread(target=log_stream, args=(worker_proc, "WORKER"), daemon=True).start()
                else:
                    break
            else:
                logger.critical("❌ Worker failed permanently after 3 restarts.")
                break

        # Check Bot
        if bot_proc and bot_proc.poll() is not None:
            logger.error(f"❌ Bot process {bot_proc.pid} exited with code {bot_proc.returncode}")
            break

        time.sleep(5)

    # Cleanup on exit
    for p in processes:
        if p.poll() is None:
            p.terminate()
    sys.exit(1)

if __name__ == "__main__":
    main()
