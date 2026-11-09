"""Reviewed application-family registry for the public Android builder.

Only trusted, repository-reviewed modules may register patterns. User objectives
are data, never executable code. New families must supply a reviewed generator
implementation before being registered.
"""
import re

_REGISTRY = {}

def register_templates(templates):
    """Register a fixed set of reviewed templates, rejecting collisions."""
    for name, spec in templates.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
            raise ValueError("invalid_template_name")
        if name in _REGISTRY:
            raise ValueError("duplicate_template_name")
        pattern, label = spec
        re.compile(pattern)
        _REGISTRY[name] = (pattern, label)

def resolve_template(objective):
    """Resolve exactly one reviewed app family; fail closed on ambiguity."""
    matches = [name for name, (pattern, _) in _REGISTRY.items()
               if re.search(pattern, objective, re.IGNORECASE)]
    if len(matches) != 1:
        raise ValueError("Jenis aplikasi tidak jelas atau belum disokong")
    return matches[0]

def available_templates():
    return tuple(sorted(_REGISTRY))
