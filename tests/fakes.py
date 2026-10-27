from app.services.ai_client import AIExplanation


class FakeAIClient:
    def __init__(self, content: str = "Resposta mockada do professor", model: str = "gemma3:4b") -> None:
        self.content = content
        self.model = model
        self.last_call: dict | None = None
        self.calls = 0

    async def generate_explanation(
        self,
        *,
        question: str,
        context: str = "",
        history: list | None = None,
        has_relevant_match: bool = True,
        has_material: bool = False,
    ) -> AIExplanation:
        self.calls += 1
        self.last_call = {
            "question": question,
            "context": context,
            "history": list(history or []),
            "has_relevant_match": has_relevant_match,
            "has_material": has_material,
        }
        return AIExplanation(content=self.content, model=self.model)
