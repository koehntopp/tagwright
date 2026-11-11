"""The library: keeps the output folder in the canonical artist/album/disc/file layout (ADR 0037).

`template` describes the layout, `planner` decides what has to move, `executor` moves files, `index` remembers
what is on disk (SQLite), `scanner` finds changes cheaply, `watcher` runs it all in a thread with a cooldown.
Nothing here imports `app`; the web layer only starts the watcher and shows its status.
"""
