from anthropic import AsyncAnthropic
import asyncio
from dotenv import load_dotenv
from quart import Quart, request, jsonify, Response
from functools import wraps
from google import genai
import json
from openai import AsyncOpenAI
import os
import logging

load_dotenv()

app = Quart(__name__)

root = logging.getLogger()
for handler in root.handlers[:]:
    root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(process)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

API_TOKEN = os.environ.get("API_TOKEN", "default_token")

def token_required(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        if token != API_TOKEN:
            return jsonify({'message': 'Invalid token!'}), 401

        return await f(*args, **kwargs)

    return decorated

def provider(model):
    if model.startswith('claude'):
        return 'anthropic'
    elif model.startswith('gemini'):
        return 'google'
    elif model.startswith('gpt') or model.startswith('o'):
        return 'openai'
    else:
        return 'unknown'

async def anthropic_stream(model, prompt, request_id):
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    usage = None
    if 'opus' in model:
        max_tokens = 32000
    else:
        max_tokens = 64000

    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for event in stream:
            if event.type == "message_stop" and hasattr(event.message, 'usage'):
                metadata = event.message.usage
                usage = {
                    "input": metadata.input_tokens,
                    "output": metadata.output_tokens
                }
            elif event.type == "content_block_delta":
              yield {"type": "delta", "text": event.delta.text}

        logger.info(f"[{request_id}] Streaming completed")
        yield {"type": "done", "usage": usage}


async def openai_stream(model, prompt, request_id):
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    if model.startswith('gpt-5') or model.startswith('o'):
      temperature = 1
    else:
      temperature = 0.3

    stream = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        temperature=temperature,
        stream_options={"include_usage": True}
    )

    usage = None
    async for chunk in stream:
        if chunk.choices and chunk.choices[0] and chunk.choices[0].delta.content:
            delta = chunk.choices[0].delta.content
            yield {"type": "delta", "text": delta}
        elif chunk.usage:
            usage = {
                "input": chunk.usage.prompt_tokens,
                "output": chunk.usage.total_tokens - chunk.usage.prompt_tokens
            }

    logger.info(f"[{request_id}] Streaming completed")
    yield {"type": "done", "usage": usage}

async def google_stream(model, prompt, request_id):
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    usage = None
    # Pseudocode: open streaming request
    stream = client.models.generate_content_stream(
        contents=[{"role": "user", "parts":[{"text": prompt}]}],
        model=model,
        # maybe streaming=True or the method name implies streaming
    )

    for resp in stream:
        # Each `resp` may contain partial content and optionally usage
        text = resp.candidates[0].content.parts[0].text
        if hasattr(resp, "usage_metadata"):
            metadata = resp.usage_metadata
            usage = {
                "input": metadata.prompt_token_count,
                "output": metadata.total_token_count - metadata.prompt_token_count
            }
        if text:
            yield {"type": "delta", "text": text}

    logger.info(f"[{request_id}] Streaming completed")
    yield {"type": "done", "usage": usage}

@app.route("/stream", methods=["POST"])
@token_required
async def process_stream():
    """
    Streaming LLM Endpoint
    Body:
      {
        "model": "gpt-4o-mini",
        "prompt": "Explain streaming requests..."
      }
    """
    data = await request.get_json(force=True)
    model = data.get("model", "gpt-4o-mini")
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    prov = provider(model)
    if prov == "unknown":
        return jsonify({"error": f"Unsupported model: {model}"}), 400

    request_id = os.urandom(8).hex()

    logger.info(f"[{request_id}] Streaming from {prov} ({model})")

    async def generate():
        try:
            match prov:
                case "anthropic":
                    async for chunk in anthropic_stream(model, prompt, request_id):
                        yield f"data: {json.dumps(chunk)}\n\n"
                case "openai":
                    async for chunk in openai_stream(model, prompt, request_id):
                        yield f"data: {json.dumps(chunk)}\n\n"
                case "google":
                    async for chunk in google_stream(model, prompt, request_id):
                        yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.error(f"[{request_id}] Error during streaming: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    response = Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
    response.timeout = None  # Disable Quart's 60-second response timeout
    return response

@app.route('/health', methods=['GET'])
async def health_check():
    return jsonify({"status": "healthy"}), 200
