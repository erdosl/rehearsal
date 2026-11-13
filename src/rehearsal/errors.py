"""User-facing errors contain safe explanations, never raw input payloads."""


class RehearsalError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ConfigError(RehearsalError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_configuration", message)


class InventoryError(RehearsalError):
    pass
