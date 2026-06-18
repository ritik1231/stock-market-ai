import asyncio
import json
import logging

from groq import AsyncGroq, RateLimitError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Accumulated token usage across all calls in this process
_token_usage: dict[str, int] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


def get_token_usage() -> dict[str, int]:
    """Return a snapshot of accumulated token usage."""
    return dict(_token_usage)


def _update_usage(usage) -> None:
    if usage is None:
        return
    _token_usage["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
    _token_usage["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
    _token_usage["total_tokens"] += getattr(usage, "total_tokens", 0) or 0


def _strip_markdown(text: str) -> str:
    """Remove markdown code fences that Groq sometimes wraps JSON in."""
    s = text.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        # drop first line (```json) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        s = "\n".join(inner).strip()
    return s


async def groq_complete(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.3-70b-versatile",
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> str:
    """Call Groq chat completion with up to 3 retries on RateLimitError (1s / 2s / 4s backoff)."""
    client = _get_client()
    _retry_delays = [1, 2, 4]
    last_exc: Exception | None = None

    for attempt in range(len(_retry_delays) + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            _update_usage(response.usage)
            logger.debug(
                "groq_complete ok: model=%s tokens=%s",
                model,
                getattr(response.usage, "total_tokens", "?"),
            )
            return response.choices[0].message.content or ""
        except RateLimitError as exc:
            last_exc = exc
            if attempt < len(_retry_delays):
                delay = _retry_delays[attempt]
                logger.warning(
                    "Groq rate limited (attempt %d/4), retrying in %ds", attempt + 1, delay
                )
                await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]


async def groq_sentiment(text: str, ticker: str) -> dict:
    """Return sentiment analysis as {"score": float, "label": str, "reasoning": str}."""
    system_prompt = (
        "You are a financial sentiment analyzer. "
        "Analyze the sentiment of the provided news text about the given stock ticker. "
        "Respond ONLY with valid JSON and no markdown or explanation:\n"
        '{"score": <float -1.0 to 1.0>, "label": "<BULLISH|BEARISH|NEUTRAL>", "reasoning": "<brief>"}'
    )
    user_prompt = f"Ticker: {ticker}\n\nNews:\n{text[:4000]}"

    for attempt in range(2):
        raw = await groq_complete(system_prompt, user_prompt, temperature=0.0, max_tokens=256)
        try:
            return json.loads(_strip_markdown(raw))
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt == 0:
                logger.warning("groq_sentiment malformed JSON, retrying: %s", exc)
            else:
                logger.error("groq_sentiment parse failed after retry. raw=%r", raw)

    return {"score": 0.0, "label": "NEUTRAL", "reasoning": "Response parse failed"}


async def groq_summarize(text: str, context: str, max_words: int = 200) -> str:
    """Summarize text + context in at most max_words words."""
    system_prompt = (
        f"You are a concise financial analyst. "
        f"Summarize the provided text and context in no more than {max_words} words. "
        "Focus on key facts, risks, and opportunities."
    )
    user_prompt = f"Text:\n{text[:3000]}\n\nContext:\n{context[:1000]}"
    return await groq_complete(system_prompt, user_prompt, temperature=0.1, max_tokens=512)


async def groq_synthesize_signal(research: dict, quant: dict, risk: dict) -> dict:
    """Synthesize a final trading signal from sub-agent outputs.

    Returns {"signal": "BUY|SELL|HOLD", "confidence": float, "summary": str, "key_factors": list}.
    """
    system_prompt = (
        "You are a senior trading signal synthesizer. "
        "Given research, quantitative, and risk analysis for a stock, produce a final trading signal. "
        "Respond ONLY with valid JSON and no markdown:\n"
        '{"signal": "<BUY|SELL|HOLD>", "confidence": <float 0.0-1.0>, '
        '"summary": "<2-3 sentence summary>", "key_factors": ["<factor1>", ...]}'
    )
    user_prompt = (
        f"Research Analysis:\n{json.dumps(research, default=str)}\n\n"
        f"Quantitative Analysis:\n{json.dumps(quant, default=str)}\n\n"
        f"Risk Analysis:\n{json.dumps(risk, default=str)}"
    )

    raw = await groq_complete(system_prompt, user_prompt, temperature=0.1, max_tokens=512)
    try:
        return json.loads(_strip_markdown(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("groq_synthesize_signal parse failed: %s\nraw=%r", exc, raw)
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "summary": "Signal synthesis failed due to a response parse error.",
            "key_factors": [],
        }
