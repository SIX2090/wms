"""Known, safe-to-display validation failures during document import."""


class InactiveMaterialImportError(ValueError):
    """A material in an import is disabled and cannot create a new document."""
