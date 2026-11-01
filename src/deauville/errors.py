class FestivalError(Exception):
    """Base of every error of the festival: the message is a sentence."""


class NotFound(FestivalError):
    """A slug or an id that does not exist (404)."""


class Conflict(FestivalError):
    """Valid request, but it clashes with the schedule or the state (409)."""


class Invalid(FestivalError):
    """A value that breaks a rule (422)."""
    