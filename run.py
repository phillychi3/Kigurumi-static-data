import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app", host="127.0.0.1", port=8001, reload=True, log_level="info"
    )
