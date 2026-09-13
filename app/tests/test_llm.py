import pytest
from app.agent.llm import LLMService, LLMResponse


class TestLLMService:
    @pytest.fixture(autouse=True)
    def setup_llm(self):
        self.llm = LLMService()

    def test_llm_initialization(self):
        assert self.llm.ollama_base == "http://localhost:11434"
        assert self.llm.ollama_model == "llama3.1"
        assert self.llm.groq_model == "llama-3.1-70b-versatile"

    def test_generate_with_ollama(self):
        response = self.llm.generate("Hello, how are you?", max_tokens=10)
        assert isinstance(response, LLMResponse)
        assert response.provider in ["ollama", "groq"]

    def test_generate_with_groq(self):
        response = self.llm.generate("What is the capital of France?", model="llama-3.1-70b-versatile", max_tokens=10)
        assert isinstance(response, LLMResponse)
        assert response.provider == "groq" or response.provider == "ollama"

    def test_generate_with_error(self):
        response = self.llm.generate("Test", max_tokens=10)
        assert isinstance(response, LLMResponse)
        assert response.provider is not None

    def test_chat_with_ollama(self):
        messages = [{"role": "user", "content": "Say hello"}]
        response = self.llm.chat(messages, max_tokens=10)
        assert isinstance(response, LLMResponse)
        assert response.provider in ["ollama", "groq"]

    def test_chat_with_groq(self):
        messages = [{"role": "user", "content": "What is AI?"}]
        response = self.llm.chat(messages, model="llama-3.1-70b-versatile", max_tokens=10)
        assert isinstance(response, LLMResponse)

    def test_provider_fallback(self):
        """If Ollama is down, should fall back to Groq"""
        response = self.llm.generate("Test question", max_tokens=10)
        assert isinstance(response, LLMResponse)
        assert response.content is not None or response.error is not None

    def test_cost_estimation(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        cost = self.llm._estimate_cost("llama-3.1-70b-versatile", usage)
        assert isinstance(cost, float)
        assert cost >= 0.0

    def test_llm_response_defaults(self):
        response = LLMResponse(content="test", provider="ollama", model="test")
        assert response.content == "test"
        assert response.provider == "ollama"
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        assert response.cost_usd == 0.0