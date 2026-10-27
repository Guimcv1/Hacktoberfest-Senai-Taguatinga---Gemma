from app.services.ai_client import AIExplanation


class FakeAIClient:
    def __init__(
        self,
        content: str = "Resposta mockada do professor",
        model: str = "gemma3:4b",
        completions: list[str | BaseException] | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.last_call: dict | None = None
        self.last_completion: dict | None = None
        self.calls = 0
        self.completion_calls = 0
        self._completions = list(completions) if completions is not None else None

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

    async def generate_completion(
        self,
        *,
        messages: list[dict[str, str]],
        json_mode: bool = False,
    ) -> AIExplanation:
        self.calls += 1
        self.completion_calls += 1
        self.last_completion = {"messages": list(messages), "json_mode": json_mode}
        if self._completions is not None:
            if not self._completions:
                raise AssertionError("FakeAIClient sem respostas restantes.")
            item = self._completions.pop(0)
            if isinstance(item, BaseException):
                raise item
            return AIExplanation(content=item, model=self.model)
        return AIExplanation(content=self.content, model=self.model)
