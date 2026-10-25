#!/usr/bin/env python3
"""Minimal stand-in for dialog(1), used by the pythondialog test suite.

It understands just enough options to exercise pythondialog's fork/exec,
output-capturing and parsing code paths without requiring a terminal.
"""

import os
import shlex
import sys


def read_args(argv):
    """Return the argument list, expanding --file if present."""
    if "--file" in argv:
        index = argv.index("--file")
        with open(argv[index + 1], encoding="utf-8") as f:
            return shlex.split(f.read())
    return argv


def main():
    args = read_args(sys.argv[1:])

    if "--print-version" in args:
        print("Version: 1.3-20250817", file=sys.stderr)
        return 0

    if "--print-maxsize" in args:
        print("MaxSize: 24,80", file=sys.stderr)
        return 0

    # Used by tests that need malformed backend output.
    forced = os.environ.get("FAKE_DIALOG_OUTPUT")
    if forced is not None:
        print(forced, file=sys.stderr)
        return 0

    if "--gauge" in args:
        # Consume the progress data until pythondialog closes the pipe.
        sys.stdin.read()
        return 0

    if "--tailboxbg" in args:
        if "--no-kill" in args:
            print("12345", file=sys.stderr)
        return 0

    if "--prgbox" in args:
        return 0

    if "--inputbox" in args or "--passwordbox" in args:
        # dialog does not append a newline to inputbox/passwordbox output.
        sys.stderr.write("hello")
        sys.stderr.flush()
        return 0

    if "--rangebox" in args:
        print("42", file=sys.stderr)
        return 0

    if "--calendar" in args:
        print("01/02/2026", file=sys.stderr)
        return 0

    if "--timebox" in args:
        print("12:34:56", file=sys.stderr)
        return 0

    if "--checklist" in args:
        # pythondialog always passes --separate-output for checklists.
        print("tag1\ntag2", file=sys.stderr)
        return 0

    if "--buildlist" in args:
        print("tag1 tag2", file=sys.stderr)
        return 0

    if "--inputmenu" in args:
        print("renamed_tag", file=sys.stderr)
        return 0

    if "--yesno" in args:
        return 1            # DIALOG_CANCEL

    if os.environ.get("FAKE_DIALOG_HELP") == "1":
        print("HELP tag", file=sys.stderr)
        return 5            # DIALOG_HELP

    if os.environ.get("FAKE_DIALOG_ERROR") == "1":
        print("simulated failure", file=sys.stderr)
        return 3            # DIALOG_ERROR

    return 0


if __name__ == "__main__":
    sys.exit(main())
