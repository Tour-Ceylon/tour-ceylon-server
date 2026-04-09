#!/usr/bin/env python3
"""
Startup script for Tour Ceylon Server
Resolves uvicorn module detection issues by running from correct directory context
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Get the directory where this script is located
    server_dir = Path(__file__).parent.absolute()
    
    # Change to the server directory
    os.chdir(server_dir)
    
    # Add the server directory to Python path
    sys.path.insert(0, str(server_dir))
    
    # Set environment variables
    env = os.environ.copy()
    env['PYTHONPATH'] = str(server_dir)
    
    # Check if .env file exists and load DATABASE_URL
    env_file = server_dir / '.env'
    if env_file.exists():
        print("Loading environment from .env file...")
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    env[key] = value
    
    # Start uvicorn
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', '8000',
        '--reload',
        '--reload-dir', '.',
        '--app-dir', '.'
    ]
    
    print(f"Starting server from: {server_dir}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, env=env, cwd=server_dir)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()