"""Entry point for the MCPB bundle: start the cr1000a-mcp server.

The package itself is installed from PyPI by uv (see the generated pyproject.toml);
this file only calls it, so the bundle stays tiny.
"""

from cr1000a_mcp import main

if __name__ == "__main__":
    main()
