# LLM streaming proxy

A simple web server for stream processing your prompts with LLMS

## Setup

1. Clone the repository
2. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Configure your environment variables in `.env`:
   ```
   # Authentication
   API_TOKEN=your_secure_token

   # API Keys
   ANTHROPIC_API_KEY=your_anthropic_api_key
   GOOGLE_API_KEY=your_google_api_key

   # Server configuration
   PORT=3000
   ```

## Running the Server

The server will start on port 3000 by default (can be changed in `.env` file). In development it uses another port due to conflict with cockpit. Use the provided `bin/dev-server` script to start the server in development mode.


## API Endpoints

### Streaming processing

```
POST /stream
```

Processes a prompt and streams response to prevent timeouts.

#### Authentication

Bearer token authentication is required. Include an `Authorization` header with the format: `Bearer your_token`, where `your_token` matches the `API_TOKEN` value set in the `.env` file.

Example:
```
Authorization: Bearer your_secure_token
```

#### Request Body

```json
{
    "model": "gpt-4o",
    "prompt": "Your instructions..."
}
```

- `model`: The AI model to use for processing. Please refer to the provider's documentation for available models.
- `prompt`: Instructions or text to be processed

References:
- [Anthropic Models](https://docs.claude.com/en/docs/about-claude/models/overview)
- [OpenAI Models](https://platform.openai.com/docs/models)
- [Google Models](https://ai.google.dev/gemini-api/docs/models)
#### Response

```json
{
    "result": "processed_definition_here"
}
```

### Health Check

```
GET /health
```

Returns a simple health status to check if the server is running.

#### Response

```json
{
    "status": "healthy"
}
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `400 Bad Request`: Missing required parameters
- `401 Unauthorized`: Missing or invalid Bearer token
- `500 Internal Server Error`: Server-side processing errors

## Example Request with cURL

```bash
curl -X POST http://localhost:5500/stream \
  -H "Authorization: Bearer your_secure_token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "prompt": "Your instructions..."
  }'
```
