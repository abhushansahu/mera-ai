from typing import Optional


class MeraAIError(Exception):
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}


class ConfigurationError(MeraAIError):
    pass


class MemoryError(MeraAIError):
    pass


class LLMError(MeraAIError):
    pass


class WorkflowError(MeraAIError):
    pass
