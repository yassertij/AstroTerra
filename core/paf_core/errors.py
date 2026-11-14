"""Structured errors. Messages must tell the user what to do next."""


class PafError(Exception):
    """Base class for all scientific-core errors."""


class LabelParseError(PafError):
    """A PDS3 label could not be parsed."""


class UnapprovedSourceError(PafError):
    """The dataset is not on the NASA-only allow-list."""


class RasterValidationError(PafError):
    """A raster or its label failed validation. `problems` lists every failed check."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("Raster validation failed:\n- " + "\n- ".join(self.problems))


class MetricError(PafError):
    """A metric cannot be computed reliably; no substitute value is returned."""
