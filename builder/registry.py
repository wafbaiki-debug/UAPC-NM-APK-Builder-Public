"""Reviewed application-family registry for the public Android builder.

Only trusted, repository-reviewed modules may register patterns. User objectives
are data, never executable code. New families must supply a reviewed generator
implementation before being registered.
"""
import re

_REGISTRY = {}

def register_templates(templates):
    """Register a fixed set of reviewed templates, rejecting collisions."""
    staged = {}
    for name, spec in templates.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
            raise ValueError("invalid_template_name")
        if name in _REGISTRY or name in staged:
            raise ValueError("duplicate_template_name")
        if not isinstance(spec, (tuple, list)) or len(spec) != 2:
            raise ValueError("invalid_template_spec")
        pattern, label = spec
        if not isinstance(pattern, str) or not isinstance(label, str) or not label.strip():
            raise ValueError("invalid_template_spec")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError("invalid_template_pattern") from exc
        staged[name] = (pattern, label)
    # Do not leave half-registered families if one module is invalid.
    _REGISTRY.update(staged)

def resolve_template(objective):
    """Resolve exactly one reviewed app family; fail closed on ambiguity."""
    matches = [name for name, (pattern, _) in _REGISTRY.items()
               if re.search(pattern, objective, re.IGNORECASE)]
    if len(matches) != 1:
        raise ValueError("Jenis aplikasi tidak jelas atau belum disokong")
    return matches[0]

def available_templates():
    return tuple(sorted(_REGISTRY))
