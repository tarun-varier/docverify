from fastapi import FastAPI
import uvicorn



app = FastAPI(
    title="DocVerify API",
    description="Simple FastAPI server",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to DocVerify API",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.get("/hello/{name}")
async def hello(name: str):
    return {
        "message": f"Hello, {name}!"
    }


if __name__ == "__main__":

    uvicorn.run(
        "app:app",
        host="0.0.0.0",   # Listen on all interfaces
        port=8000,
        reload=True
    )