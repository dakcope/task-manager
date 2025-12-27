class DomainError(Exception):
    """Base domain error."""


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ExternalServiceError(RuntimeError):
    pass