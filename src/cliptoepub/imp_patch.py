"""
Compatibility shim for the deprecated 'imp' module (Python 3.12+).
Provides a minimal subset used by older code paths.
"""
import sys
import importlib
import importlib.util
from types import ModuleType


def _find_module(name, path=None):
    """Best-effort implementation of imp.find_module using importlib."""
    try:
        spec = importlib.util.find_spec(name, path)
        if spec is None:
            return None
        # Return a tuple similar to imp.find_module: (file, pathname, description)
        # We don't return an open file handle; callers that rely on it should
        # be able to proceed with pathname + description.
        return (None, spec.origin, ("", "", 5))
    except (ImportError, AttributeError, TypeError, ValueError):
        return None


def _load_module(name, file, pathname, description):
    """Load a module from a given path using importlib."""
    spec = importlib.util.spec_from_file_location(name, pathname)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {name!r} from {pathname!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _new_module(name):
    return ModuleType(name)


def _install_shim():
    # Do not override if a real 'imp' is already present
    if 'imp' in sys.modules:
        return
    m = ModuleType('imp')
    m.find_module = _find_module  # type: ignore[attr-defined]
    m.load_module = _load_module  # type: ignore[attr-defined]
    m.new_module = _new_module    # type: ignore[attr-defined]
    # Provide imp.reload for callers that still reference it
    m.reload = importlib.reload   # type: ignore[attr-defined]
    sys.modules['imp'] = m


_install_shim()
