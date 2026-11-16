"""Allow ``python -m encnorm`` to invoke the same CLI as ``encnorm.cli``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
