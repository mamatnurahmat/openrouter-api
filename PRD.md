# Product Requirements Document (PRD)
**Product Name:** OpenRouter API Wrapper & Smart Fallback Service
**Version:** 1.0.0

## 1. Introduction
The OpenRouter API Wrapper is a lightweight, dockerized FastAPI service that acts as a resilient proxy between end-users (or internal applications) and OpenRouter's LLM API. Its primary goal is to ensure high availability and reliability when querying free or rate-limited LLM models.

## 2. Problem Statement
OpenRouter provides access to various open-source LLMs, many of which have free tiers. However, these free endpoints frequently suffer from severe rate-limiting (HTTP 429), downtime (HTTP 5xx), or model deprecation (HTTP 404). Without a fallback mechanism, applications relying on a single model will fail outright.

## 3. Product Goals
1. Provide a drop-in replacement API for OpenAI/OpenRouter chat completions.
2. Ensure 99% uptime for chat requests by intelligently falling back to other models when the primary model fails.
3. Automatically discover available ("ready") models dynamically from OpenRouter.
4. Maintain a clean, interactive API documentation surface (Swagger UI).

## 4. Key Features & Requirements

### 4.1. Core Endpoints
- **`POST /chat`**: Receives a standardized chat request (message, model). Relays the prompt to OpenRouter.
- **`GET /models/ready`**: Fetches the live list of models from OpenRouter, filters and prioritizes free/available models, and returns up to 5 models.

### 4.2. Smart Fallback Mechanism
- When `POST /chat` receives an `APIStatusError` containing codes `429`, `404`, `500`, `502`, `503`, or `504`, the system must intercept the failure.
- The system will call the `/models/ready` internal logic to fetch active models.
- The system will save the array of available models locally to `ready_models.json`.
- The system will iterate through this new array and retry the original prompt until a successful response is received.
- If the dynamic fetch fails, the system falls back to a statically defined `FALLBACK_MODELS` list located in the `.env` configuration.

### 4.3. Configuration Management
- Environment variables must be stored securely in a `.env` file (ignored by git).
- The `.env` file dictates the `OPENROUTER_API_KEY`, `DEFAULT_MODEL`, and static `FALLBACK_MODELS`.

### 4.4. Containerization
- Must use a lightweight Python 3.11 image.
- Must provide a `docker-compose.yml` that maps ports and volumes seamlessly for local development.

## 5. Non-Functional Requirements
- **Performance**: Fallback loops must execute rapidly to reduce user wait time.
- **Security**: The `OPENROUTER_API_KEY` must never be exposed or hardcoded in the application repository.
- **Extensibility**: Easily upgradeable to streaming responses in future iterations.

## 6. Future Roadmap / TODO
- [ ] **Timeout-based Model Switching**: Implement a strict 9-second timeout limit for chat completions. If a model fails to respond within 9 seconds, automatically abort the request and trigger the fallback mechanism to switch to the next available model in the queue.
