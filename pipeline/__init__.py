"""The Tagwright pipeline: the tag-fixing steps behind "Run fixes" (ADR 0036).

Each module is one step or one shared helper; `app.py` is only the web layer. No module here
imports `app`; settings and paths come in as arguments.
"""
