"""Coordenação das inferências e do unload neste processo.

O Ollama é compartilhado. Este cadeado impede descarregar o modelo no meio de uma
resposta e impede novas inferências enquanto o unload corre. Com vários workers
ou instâncias, cada processo tem o seu próprio estado: o lock não atravessa a
rede. Nesse caso, rode um único worker ou descarregue só quando não houver carga.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.services.ai_client import AIClientError


class AIBusyUnloadingError(AIClientError):
    def __init__(self) -> None:
        super().__init__("O modelo está sendo descarregado. Tente novamente em instantes.")


class AIInferencesInProgressError(AIClientError):
    def __init__(self) -> None:
        super().__init__(
            "Há uma resposta da IA em andamento. Aguarde terminar antes de descarregar o modelo."
        )


class AIUnloadInProgressError(AIClientError):
    def __init__(self) -> None:
        super().__init__("Já há um descarregamento em andamento. Aguarde e tente de novo.")


class InferenceGate:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._in_flight = 0
        self._unloading = False

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def unloading(self) -> bool:
        return self._unloading

    def reset(self) -> None:
        self._in_flight = 0
        self._unloading = False

    @asynccontextmanager
    async def inference(self) -> AsyncIterator[None]:
        async with self._lock:
            if self._unloading:
                raise AIBusyUnloadingError()
            self._in_flight += 1
        try:
            yield
        finally:
            async with self._lock:
                self._in_flight -= 1

    @asynccontextmanager
    async def unload(self) -> AsyncIterator[None]:
        async with self._lock:
            if self._unloading:
                raise AIUnloadInProgressError()
            if self._in_flight > 0:
                raise AIInferencesInProgressError()
            self._unloading = True
        try:
            yield
        finally:
            async with self._lock:
                self._unloading = False


_gate = InferenceGate()


def get_inference_gate() -> InferenceGate:
    return _gate
