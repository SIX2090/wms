"""Temporary evidence destination shared by these synthetic regression cases."""
from contextvars import ContextVar

_evidence = ContextVar('audit_evidence_directory')


def evidence_dir():
    return _evidence.get()
