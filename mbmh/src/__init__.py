"""mbmh source package.

The repository uses multiple top-level `src/` directories across services. This
`__init__.py` ensures `import src.*` inside `mbmh` tests resolves to this
package rather than another service's `src` package that may be installed in
the same editable environment.
"""

__all__: list[str] = []
