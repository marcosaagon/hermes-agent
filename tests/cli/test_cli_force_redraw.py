"""Tests for CLI redraw helpers used to recover from terminal buffer drift.

Covers:
  - _force_full_redraw (#8688 cmux tab switch, /redraw, Ctrl+L)
  - the resize handler we install over prompt_toolkit's _on_resize (#5474)

Both behaviors are exercised against fake prompt_toolkit renderer/output
objects — we're asserting the escape sequences the CLI sends, not that
the terminal physically repainted.
"""

from unittest.mock import MagicMock

import pytest

import cli as cli_mod
from cli import HermesCLI


@pytest.fixture
def bare_cli():
    """A HermesCLI with no __init__ — we only exercise the redraw helper."""
    cli = object.__new__(HermesCLI)
    return cli


class TestForceFullRedraw:
    def test_no_app_is_safe(self, bare_cli):
        # _force_full_redraw must be a no-op when the TUI isn't running.
        bare_cli._app = None
        bare_cli._force_full_redraw()  # must not raise

    def test_missing_app_attr_is_safe(self, bare_cli):
        # Simulate HermesCLI before the TUI has ever been constructed.
        bare_cli._force_full_redraw()  # must not raise

    def test_sends_full_clear_replays_then_invalidates(self, bare_cli, monkeypatch):
        app = MagicMock()
        out = app.renderer.output
        bare_cli._app = app
        events = []
        out.reset_attributes.side_effect = lambda: events.append("reset_attrs")
        out.erase_screen.side_effect = lambda: events.append("erase")
        out.cursor_goto.side_effect = lambda *_: events.append("home")
        out.flush.side_effect = lambda: events.append("flush")
        app.renderer.reset.side_effect = lambda **_: events.append("renderer_reset")
        monkeypatch.setattr(cli_mod, "_replay_output_history", lambda: events.append("replay"))
        app.invalidate.side_effect = lambda: events.append("invalidate")

        bare_cli._force_full_redraw()

        # Must erase screen, home cursor, and flush — in that order.
        out.reset_attributes.assert_called_once()
        out.erase_screen.assert_called_once()
        out.cursor_goto.assert_called_once_with(0, 0)
        out.flush.assert_called_once()

        # Must reset prompt_toolkit's tracked screen/cursor state so the
        # next incremental redraw starts from a clean (0, 0) origin.
        app.renderer.reset.assert_called_once_with(leave_alternate_screen=False)

        # Must schedule a repaint.
        app.invalidate.assert_called_once()
        assert events == [
            "reset_attrs",
            "erase",
            "home",
            "flush",
            "renderer_reset",
            "replay",
            "invalidate",
        ]

    def test_resize_clears_scrollback_and_replays(self, bare_cli, monkeypatch):
        """Resize recovery clears viewport+scrollback and replays history.

        Earlier iterations (#25975, #24403, #25972, #25974, and the first
        commits on this branch) tried various "preserve screen + suppress
        chrome" or "clear viewport only + sync write_raw" combinations.
        All of them either left reflowed bars on screen or stacked
        content across repeated resizes because ``\\x1b[2J`` clears the
        viewport but leaves scrollback intact — so the previous resize's
        already-reflowed chrome stays above the visible region.

        The current approach mirrors what claude-code's Ink renderer does:
        write ``\\x1b[2J\\x1b[3J\\x1b[H`` (viewport + scrollback + home) and
        then replay tracked history through prompt_toolkit's own output
        pipeline (``_pt_print`` via ``_replay_output_history``).  This
        keeps colors/attributes consistent with pt's renderer state on
        the next frame; ``write_raw`` of recorded ANSI bypasses that
        state and produces white-on-white artifacts.

        ``_status_bar_suppressed_after_resize`` must be False after
        recovery so the next invalidate paints the input bar / status bar
        normally.  Leaving it True (the previous strategy) made the input
        bar disappear entirely.

        ``original_on_resize`` must NOT be invoked: its ``renderer.erase``
        does ``cursor_up(stale_logical_y) + erase_down`` which is the
        original duplication source.
        """
        app = MagicMock()
        events: list = []
        out = app.renderer.output
        out.reset_attributes.side_effect = lambda: events.append("reset_attrs")
        out.erase_screen.side_effect = lambda: events.append("erase_screen")
        out.write_raw.side_effect = lambda s: events.append(("write_raw", s))
        out.cursor_goto.side_effect = lambda *_: events.append("home")
        out.flush.side_effect = lambda: events.append("flush")
        app.renderer.reset.side_effect = lambda **_: events.append("renderer_reset")
        app.invalidate.side_effect = lambda: events.append("invalidate")
        monkeypatch.setattr(cli_mod, "_replay_output_history", lambda: events.append("replay"))

        original_called = []
        original_on_resize = lambda: original_called.append(True)

        # Set suppression True so we can verify recovery clears it.
        bare_cli._status_bar_suppressed_after_resize = True
        bare_cli._recover_after_resize(app, original_on_resize)

        # Must erase BOTH the viewport (\x1b[2J via erase_screen) AND
        # scrollback (\x1b[3J via write_raw).  Without the scrollback
        # erase, repeated resizes stack content above the viewport.
        assert "erase_screen" in events, events
        assert any(
            isinstance(e, tuple) and e[0] == "write_raw" and "\x1b[3J" in e[1]
            for e in events
        ), f"Expected \\x1b[3J in write_raw payload: {events}"
        assert "home" in events, events
        # Replay must run (banner + chat repainted above prompt).
        assert "replay" in events, events
        # Invalidate must be last so pt's next render reflects new dims.
        assert events[-1] == "invalidate", events
        # original_on_resize is intentionally NOT called — its erase()
        # is what was leaking reflowed chrome.
        assert original_called == [], "original_on_resize must not be invoked"
        # Suppression must be cleared so input bar / status bar reappear.
        assert bare_cli._status_bar_suppressed_after_resize is False

    def test_force_redraw_uses_full_screen_clear_without_scrollback_clear(self, bare_cli):
        app = MagicMock()
        bare_cli._app = app

        bare_cli._force_full_redraw()

        app.renderer.output.erase_screen.assert_called_once()
        app.renderer.output.cursor_goto.assert_called_once_with(0, 0)
        app.renderer.output.write_raw.assert_not_called()

    def test_resize_recovery_is_debounced(self, bare_cli, monkeypatch):
        timers = []
        calls = []

        class FakeTimer:
            def __init__(self, delay, callback):
                self.delay = delay
                self.callback = callback
                self.cancelled = False
                self.daemon = False
                timers.append(self)

            def start(self):
                calls.append(("start", self.delay))

            def cancel(self):
                self.cancelled = True
                calls.append(("cancel", self.delay))

            def fire(self):
                self.callback()

        app = MagicMock()
        app.loop.call_soon_threadsafe.side_effect = lambda cb: cb()
        monkeypatch.setattr(cli_mod.threading, "Timer", FakeTimer)
        monkeypatch.setattr(
            bare_cli,
            "_recover_after_resize",
            lambda _app, _orig: calls.append(("recover", _orig())),
        )

        original_one = lambda: "first"
        original_two = lambda: "second"

        bare_cli._schedule_resize_recovery(app, original_one, delay=0.25)
        assert bare_cli._resize_recovery_pending is True
        bare_cli._schedule_resize_recovery(app, original_two, delay=0.25)

        assert len(timers) == 2
        assert timers[0].cancelled is True
        timers[0].fire()
        assert ("recover", "first") not in calls

        timers[1].fire()
        assert ("recover", "second") in calls
        assert bare_cli._resize_recovery_pending is False

    def test_invalidate_is_suppressed_while_resize_recovery_is_pending(self, bare_cli):
        app = MagicMock()
        bare_cli._app = app
        bare_cli._last_invalidate = 0.0
        bare_cli._resize_recovery_pending = True

        bare_cli._invalidate(min_interval=0)

        app.invalidate.assert_not_called()

    def test_swallows_renderer_exceptions(self, bare_cli):
        # If the renderer blows up for any reason, the helper must not
        # propagate — otherwise a stray Ctrl+L would crash the CLI.
        app = MagicMock()
        app.renderer.output.erase_screen.side_effect = RuntimeError("boom")
        bare_cli._app = app

        bare_cli._force_full_redraw()  # must not raise

        # invalidate() is still attempted after a renderer failure.
        app.invalidate.assert_called_once()

    def test_swallows_invalidate_exceptions(self, bare_cli):
        app = MagicMock()
        app.invalidate.side_effect = RuntimeError("boom")
        bare_cli._app = app

        bare_cli._force_full_redraw()  # must not raise
