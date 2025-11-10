"""
Patch for missing 'imp' module in Python 3.12+
This module provides compatibility for older code that still uses imp
"""
import sys
import importlib
import importlib.util
import importlib.machinery

class ImpCompat:
    """Compatibility shim for the deprecated imp module"""

    @staticmethod
    def find_module(name, path=None):
        """Find a module using importlib"""
        try:
            spec = importlib.util.find_spec(name, path)
            if spec:
                return (None, spec.origin, ('', '', 5))
        except (ImportError, AttributeError, TypeError, ValueError):
            pass
        return None

    @staticmethod
    def load_module(name, file, pathname, description):
        """Load a module using importlib"""
        spec = importlib.util.spec_from_file_location(name, pathname)
        if spec:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
        return None

    @staticmethod
    def new_module(name):
        """Create a new module"""
        from types import ModuleType
        return ModuleType(name)

# Install the compatibility shim
sys.modules['imp'] = ImpCompat()