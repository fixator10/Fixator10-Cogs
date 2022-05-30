"""
All errors used/raised by the cog.
"""


class AskedForReload(Exception):
    """This is not an error, but it's just to facilitate my life when reloading captcha."""


class NonEnabledError(Exception):
    """An error raised when the guild does not have Captcha enabled."""


class AlreadyHaveCaptchaError(Exception):
    """An error raised when a member already have a captcha object running."""


class DeletedValueError(Exception):
    """
    An error raised in case a value (Such as log channel ID or role ID) has been deleted and
    cannot be found anymore.
    """


class MissingRequiredValueError(Exception):
    """An error raised in case the guild is missing an option that must be configured."""


class LeftServerError(Exception):
    """An error raised in case the user left the server while challenging."""
