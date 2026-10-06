"""Focused submodules implementing the single-writer history database.

``voice_typer.server.history_db`` is the public facade; the implementation
lives here, split by concern: ``corruption_recovery``, ``crud_writes``,
``decorators``, ``encryption``, ``internal_api``, ``lifecycle``, ``reader``,
``retention``, ``schema``, ``search``, ``search_projection``,
``search_query``, ``write_payloads``, ``writer``, ``writer_inserts``,
``writer_submit``.

Nothing is re-exported here, import the facade or the specific submodule.
"""
