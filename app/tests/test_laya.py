import httpx
import pytest

from app.agent.laya import LayaClassificationError, LayaClassifier


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_classify_agent_route_sends_state_and_questions():
    captured = {}

    def handler(request):
        captured["json"] = request.read()
        return httpx.Response(
            200,
            json={
                "answers": {
                    "route": {
                        "choice": "qualification",
                        "probabilities": {
                            "qualification": 0.92,
                            "research": 0.08,
                        },
                    }
                }
            },
        )

    async with _client(handler) as client:
        classifier = LayaClassifier(
            client=client,
            api_key="test-key",
            endpoint="https://laya.test/classify",
        )
        result = await classifier.classify_agent_route(
            "Score this lead", {"lead_id": "lead_1"}
        )

    assert result.choice == "qualification"
    assert result.confidence == 0.92
    assert b'"message":"Score this lead"' in captured["json"]
    assert b'"lead_id":"lead_1"' in captured["json"]


@pytest.mark.asyncio
async def test_classify_rejects_missing_answers():
    def handler(request):
        return httpx.Response(200, json={"result": {}})

    async with _client(handler) as client:
        classifier = LayaClassifier(client=client, api_key="test-key")
        with pytest.raises(LayaClassificationError, match="answers"):
            await classifier.classify({}, {})


@pytest.mark.asyncio
async def test_classify_rejects_http_errors():
    def handler(request):
        return httpx.Response(503)

    async with _client(handler) as client:
        classifier = LayaClassifier(client=client, api_key="test-key")
        with pytest.raises(LayaClassificationError, match="failed"):
            await classifier.classify({}, {})
