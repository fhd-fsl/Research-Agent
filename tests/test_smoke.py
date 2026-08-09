"""Quick smoke test — verifies all imports resolve and core objects work."""

from src.config.settings import Settings, get_settings
from src.config.models import MODEL_FOR_TASK, FALLBACK_PROVIDER, PROVIDER_BASE_URLS
from src.graph.state import (
    ResearchState, create_initial_state,
    ParsedIdea, Gap, PainPointCluster, CompetitorProfile, SourceEntry,
)
from src.ingestion.source_map import SourceMap
from src.utils.llm_client import LLMClient, LLMResponse

print("All imports OK")

# Test state creation
s = create_initial_state("test idea", depth="fast")
print(f"State created: job={s['job_id']}, depth={s['depth']}, status={s['status']}")

# Test source map
sm = SourceMap()
sid = sm.add("https://example.com", "Test Page", "A snippet", "web")
print(f"Source map: {sid} -> {sm.resolve(sid)}")
tagged = sm.tag_content(sid, "hello world")
print(f"Tagged content: {tagged}")
assert tagged == f"[{sid}] hello world"

# Test model config
print(f"Tasks configured: {list(MODEL_FOR_TASK.keys())}")
print(f"Fallback provider: {FALLBACK_PROVIDER}")
print(f"Providers: {list(PROVIDER_BASE_URLS.keys())}")

# Test LLMResponse
resp = LLMResponse(
    content='{"result": "ok"}',
    provider="groq",
    model="llama-3.1-8b-instant",
    input_tokens=10,
    output_tokens=5,
)
parsed = resp.parse_json()
assert parsed == {"result": "ok"}
print(f"LLMResponse JSON parsing OK")

print("\n✓ All checks passed. Scaffold is working.")
