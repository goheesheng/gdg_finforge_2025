import asyncio
import sys
from pathlib import Path

# Add the current directory to the path so 'app' can be imported
sys.path.append(str(Path(__file__).resolve().parent))

from app.bot import main

if __name__ == "__main__":
    asyncio.run(main()) 