import logging
import sys
import os
from pathlib import Path

# Create logger
logger = logging.getLogger("tour_ceylon")
logger.setLevel(logging.INFO)

# Create formatters
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Console handler (always available)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Add handlers to logger
if not logger.handlers:
    logger.addHandler(console_handler)
    
    # Only add file handler in local development (not in serverless environments)
    # Check if we're running in a serverless environment like Vercel
    is_serverless = (
        os.getcwd().startswith('/var/task') or  # Vercel/Lambda
        os.environ.get('VERCEL') or             # Vercel environment
        os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or  # AWS Lambda
        os.environ.get('RAILWAY_ENVIRONMENT')   # Railway
    )
    
    if not is_serverless:
        try:
            # Create logs directory if it doesn't exist (local development only)
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # File handler for local development
            file_handler = logging.FileHandler(logs_dir / "app.log")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            # If file logging fails, just continue with console logging
            logger.warning("Could not create file handler, using console logging only")
