from typing import Literal

from pydantic import BaseModel, Field


class UnloadResponse(BaseModel):
    status: Literal["unloaded"]
    model: str
    message: str = Field(
        description=(
            "O Ollama aceitou o pedido de descarregamento. "
            "Não mede RAM/VRAM liberada e não apaga os arquivos do modelo."
        )
    )
