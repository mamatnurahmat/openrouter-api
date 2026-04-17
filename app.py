import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from openai import AsyncOpenAI, APIStatusError
from fastapi.responses import StreamingResponse
import json
from enum import Enum
import httpx

# Fetch the API key from environment variables (loaded by Docker Compose from .env)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Fallback models (comma separated) from .env
FALLBACK_MODELS_ENV = os.getenv("FALLBACK_MODELS", "google/gemma-2-9b-it:free,mistralai/mistral-7b-instruct:free")
FALLBACK_MODELS = [m.strip() for m in FALLBACK_MODELS_ENV.split(",") if m.strip()]
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", FALLBACK_MODELS[0] if len(FALLBACK_MODELS) > 0 else "google/gemma-2-9b-it:free")


# FastAPI app setup (Swagger UI will be automatically generated at /docs)
app = FastAPI(
    title="OpenRouter API Wrapper",
    description="A FastAPI server to interact with OpenRouter models with Smart Model Switching. Swagger UI available at /docs.",
    version="1.0.0"
)

# Initialize OpenAI async client pointing to OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY or "dummy_key", # Fallback to avoid crash on startup if key is missing
)

# Define request schema
class ChatRequest(BaseModel):
    message: str = "How many r's are in the word 'strawberry'?"
    model: str = Field(default=DEFAULT_MODEL)

class ChatResponse(BaseModel):
    response: str
    model_used: str

@app.post("/chat", response_model=ChatResponse, summary="Send a chat message", tags=["Chat"])
async def chat_endpoint(request: ChatRequest):
    """
    Sends a message to the specified OpenRouter model. If it hits a 429 Rate Limit error, it will smartly switch to other free models defined in FALLBACK_MODELS.
    """
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is not properly set in the .env file.")
        
    model_name = request.model
    models_to_try = [model_name]
    last_error = None
    fetched_fallbacks = False
    
    while models_to_try:
        current_model = models_to_try.pop(0)
        try:
            print(f"Attempting with model: {current_model}")
            
            # TODO: Implement 9-second timeout limit. 
            # If the response takes longer than 9 seconds, abort this request
            # and automatically throw a Timeout exception to trigger the fallback logic.
            completion = await client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": request.message}]
            )
            return ChatResponse(
                response=completion.choices[0].message.content,
                model_used=current_model
            )
        except Exception as e:
            is_fallbackable = False
            if isinstance(e, APIStatusError):
                if e.status_code in [429, 404, 500, 502, 503, 504] or "429" in str(e):
                    is_fallbackable = True
            elif "429" in str(e):
                is_fallbackable = True
                
            if is_fallbackable:
                print(f"[Fallback Triggered] Model {current_model} failed. Error code/message: {str(e)}")
                last_error = e
                
                if not fetched_fallbacks:
                    try:
                        print("Fetching ready models from OpenRouter to use as fallback...")
                        ready_data = await get_ready_models()
                        ready_list = ready_data.get("ready_models", [])
                        
                        # Save to ready_models.json
                        with open("ready_models.json", "w") as f:
                            json.dump(ready_list, f, indent=2)
                        print("Saved fetched models to ready_models.json")
                        
                        # Add newly fetched models to queue
                        for m in ready_list:
                            new_model = m["id"]
                            if new_model not in models_to_try and new_model != current_model:
                                models_to_try.append(new_model)
                    except Exception as fetch_e:
                        print(f"Failed to fetch dynamic ready models, falling back to .env list. Error: {fetch_e}")
                        for m in FALLBACK_MODELS:
                            if m not in models_to_try and m != current_model:
                                models_to_try.append(m)
                                
                    fetched_fallbacks = True
                continue
            else:
                status_code = getattr(e, "status_code", 500)
                raise HTTPException(status_code=status_code, detail=str(e))
                
    raise HTTPException(status_code=429, detail=f"All models failed. Last error: {str(last_error)}")

@app.get("/models/ready", summary="Get 5 ready models", tags=["Models"])
async def get_ready_models():
    """
    Fetch up to 5 available models directly from OpenRouter API.
    Prioritizes free models.
    """
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get("https://openrouter.ai/api/v1/models")
            response.raise_for_status()
            data = response.json()
            
            models = data.get("data", [])
            ready_models = []
            
            # Filter to prioritize free models
            for m in models:
                pricing = m.get("pricing", {})
                if pricing.get("prompt") == "0" and pricing.get("completion") == "0" or pricing.get("prompt") == "0.0":
                    ready_models.append({
                        "id": m["id"],
                        "name": m.get("name", "Unknown"),
                        "pricing": "Free"
                    })
                if len(ready_models) >= 5:
                    break
            
            # If not enough free models, backfill with others
            if len(ready_models) < 5:
                for m in models:
                    if not any(rm["id"] == m["id"] for rm in ready_models):
                        ready_models.append({
                            "id": m["id"],
                            "name": m.get("name", "Unknown"),
                            "pricing": "Paid"
                        })
                    if len(ready_models) >= 5:
                        break
                        
            return {"ready_models": ready_models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models from OpenRouter: {str(e)}")