import socket
import time
import os
import sys

def wait_for_db():
    host = os.getenv("DB_HOST", "db")
    port = int(os.getenv("DB_PORT", 5432))
    retries = 30
    
    print(f"Waiting for database at {host}:{port}...")
    
    for i in range(retries):
        try:
            with socket.create_connection((host, port), timeout=2):
                print("Database is ready!")
                return
        except (OSError, ConnectionRefusedError):
            print(f"Database unavailable, retrying ({i+1}/{retries})...")
            time.sleep(2)
            
    print("Database unreachable after retries.")
    sys.exit(1)

if __name__ == "__main__":
    wait_for_db()
