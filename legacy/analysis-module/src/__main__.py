"""Allow `python -m analysis_module` style execution when loaded as a package."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
