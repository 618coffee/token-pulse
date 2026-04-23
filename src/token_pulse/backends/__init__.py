from .base import Backend
from .claude_code import ClaudeCodeBackend
from .copilot import CopilotBackend

__all__ = ["Backend", "ClaudeCodeBackend", "CopilotBackend", "get_backend"]


def get_backend(name: str, **kwargs) -> Backend:
    if name == "claude-code":
        return ClaudeCodeBackend(**kwargs)
    if name == "copilot":
        return CopilotBackend(**kwargs)
    raise ValueError(f"Unknown backend: {name!r}. Choose 'claude-code' or 'copilot'.")
