import click


class WapuCLIError(click.ClickException):
    def __init__(self, message: str, exit_code: int = 1, status_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.status_code = status_code
