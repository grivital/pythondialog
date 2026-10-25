#!/usr/bin/env python3
"""Minimal stand-in for dialog(1), used by the pythondialog test suite.

It understands just enough options to exercise pythondialog's fork/exec,
output-capturing and parsing code paths without requiring a terminal.
"""

import os
import shlex
import sys


# Characters escaped by dialog inside quoted strings (see util.c in dialog).
FIX_SINGLE = "\n\\"
FIX_DOUBLE = "\n\\[]{}?*;`~#$^&()|<>"


def read_args(argv):
    """Return the argument list, expanding --file if present."""
    if "--file" in argv:
        index = argv.index("--file")
        with open(argv[index + 1], encoding="utf-8") as f:
            return shlex.split(f.read())
    return argv


def option_value(args, name):
    if name in args:
        index = args.index(name)
        if index + 1 < len(args):
            return args[index + 1]
    return None


def quote_delimiter(args):
    if "--single-quoted" in args:
        return "'"
    if "--quoted" in args:
        return '"'
    return None


def must_quote(value, quote):
    if not value:
        return True
    fix = FIX_SINGLE if quote == "'" else FIX_DOUBLE
    return (quote in value
            or any(c in value for c in "\n\t ")
            or any(c in value for c in fix))


def quote_value(value, quote):
    if quote is None or not must_quote(value, quote):
        return value

    fix = FIX_SINGLE if quote == "'" else FIX_DOUBLE
    out = [quote]
    for char in value:
        if char == quote or char in fix:
            out.append("\\")
        out.append(char)
    out.append(quote)
    return "".join(out)


def output_separator(args, default):
    return (option_value(args, "--output-separator")
            or option_value(args, "--separator")
            or default)


def env_values(name, default):
    return os.environ.get(name, default).split(",")


def emit_list(args, values, default_separator, *,
              force_quote=False, trailing=False, leading=False):
    separator = output_separator(args, default_separator)
    quote = quote_delimiter(args)
    if force_quote and quote is None:
        quote = '"'
    text = separator.join(quote_value(value, quote) for value in values)
    if leading:
        text = separator + text
    if trailing:
        text += separator
    sys.stderr.write(text)
    sys.stderr.flush()


def emit_scalar(args, value, *, force_quote=False):
    quote = quote_delimiter(args)
    if force_quote and quote is None:
        quote = '"'
    sys.stderr.write(quote_value(value, quote))
    sys.stderr.flush()


# Widgets that call dlg_does_output() in dialog: they contribute a segment
# (possibly empty) to a --and-widget chain.
OUTPUT_CAPABLE = {
    "--inputbox", "--passwordbox", "--menu", "--inputmenu",
    "--checklist", "--buildlist", "--radiolist", "--treeview",
    "--form", "--passwordform", "--mixedform", "--editbox",
    "--fselect", "--dselect", "--calendar", "--timebox", "--rangebox",
}

CHAIN_WIDGETS = OUTPUT_CAPABLE | {
    "--yesno", "--msgbox", "--infobox", "--pause", "--textbox",
    "--tailbox", "--tailboxbg", "--progressbox", "--programbox",
    "--prgbox", "--gauge", "--mixedgauge",
}


def write_argv(args):
    path = os.environ.get("FAKE_DIALOG_ARGV_FILE")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            for arg in args:
                f.write(arg + "\n")


def find_widget(group):
    for arg in group:
        if arg in CHAIN_WIDGETS:
            return arg
    return None


def widget_output(widget):
    if widget in ("--inputbox", "--passwordbox"):
        return os.environ.get("FAKE_DIALOG_INPUT", "hello")
    if widget in ("--menu", "--inputmenu"):
        return os.environ.get("FAKE_DIALOG_MENU_VALUE", "tag")
    if widget in ("--checklist", "--buildlist"):
        return env_values("FAKE_DIALOG_LIST_VALUES", "tag1,tag2")[0]
    if widget in ("--radiolist", "--treeview"):
        return env_values("FAKE_DIALOG_LIST_VALUES", "tag1")[0]
    if widget in ("--form", "--passwordform", "--mixedform"):
        return env_values("FAKE_DIALOG_FORM_VALUES", "value1,value2")[0]
    if widget == "--editbox":
        return env_values("FAKE_DIALOG_EDITBOX_LINES", "line1,line2")[0]
    if widget in ("--fselect", "--dselect"):
        return "/tmp"
    if widget == "--calendar":
        return "01/02/2026"
    if widget == "--timebox":
        return "12:34:56"
    if widget == "--rangebox":
        return "42"
    return ""


def widget_code(widget):
    if widget == "--yesno":
        return 1                # DIALOG_CANCEL
    if widget == "--menu" and os.environ.get("FAKE_DIALOG_ESC") == "1":
        return 2                # DIALOG_ESC
    return 0


def run_chain(args):
    separator = option_value(args, "--separate-widget") or "\t"

    groups = []
    current = []
    for arg in args:
        if arg == "--and-widget":
            groups.append(current)
            current = []
        else:
            current.append(arg)
    groups.append(current)

    output_count = 0
    chunks = []
    ret = 0

    for group in groups:
        widget = find_widget(group)
        ret = widget_code(widget)

        if widget in OUTPUT_CAPABLE:
            output_count += 1

        # show_result() only prints output (and the preceding separator)
        # for OK, EXTRA, HELP and ITEM_HELP.
        if ret in (0, 4, 5, 6):
            if widget in OUTPUT_CAPABLE and output_count > 1:
                chunks.append(separator)
            chunks.append(widget_output(widget))

        if ret == 2:            # ESC stops the chain
            break

    sys.stderr.write("".join(chunks))
    sys.stderr.flush()
    return ret


def main():
    args = read_args(sys.argv[1:])
    write_argv(args)

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

    if os.environ.get("FAKE_DIALOG_HELP") == "1":
        print("HELP tag", file=sys.stderr)
        return 5            # DIALOG_HELP

    if os.environ.get("FAKE_DIALOG_ERROR") == "1":
        print("simulated failure", file=sys.stderr)
        return 3            # DIALOG_ERROR

    if "--and-widget" in args:
        return run_chain(args)

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
        emit_scalar(args, os.environ.get("FAKE_DIALOG_INPUT", "hello"))
        return 0

    if "--form" in args or "--passwordform" in args or "--mixedform" in args:
        emit_list(args, env_values("FAKE_DIALOG_FORM_VALUES",
                                   "value1,value2"),
                  "\n", trailing=True)
        return 0

    if "--editbox" in args:
        emit_list(args, env_values("FAKE_DIALOG_EDITBOX_LINES",
                                   "line1,line2"),
                  "\n", trailing=True)
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
        emit_list(args, env_values("FAKE_DIALOG_LIST_VALUES",
                                   "tag1,tag2"),
                  "\n", trailing=True)
        return 0

    if "--buildlist" in args:
        separate = "--separate-output" in args
        has_output_separator = bool(
            option_value(args, "--output-separator")
            or option_value(args, "--separator"))
        emit_list(args, env_values("FAKE_DIALOG_LIST_VALUES",
                                   "tag1,tag2"),
                  "\n" if separate else " ",
                  force_quote=not separate,
                  leading=has_output_separator)
        return 0

    if "--radiolist" in args:
        values = env_values("FAKE_DIALOG_LIST_VALUES", "tag1")
        emit_scalar(args, values[0])
        return 0

    if "--treeview" in args:
        values = env_values("FAKE_DIALOG_LIST_VALUES", "tag1")
        emit_scalar(args, values[0],
                    force_quote="--separate-output" not in args)
        return 0

    if "--inputmenu" in args:
        if os.environ.get("FAKE_DIALOG_INPUTMENU_RENAMED") == "1":
            tag = os.environ.get("FAKE_DIALOG_INPUTMENU_TAG", "tag1")
            item = os.environ.get("FAKE_DIALOG_INPUTMENU_ITEM", "new item")
            quote = quote_delimiter(args)
            sys.stderr.write("RENAMED {0} {1}".format(
                quote_value(tag, quote), quote_value(item, quote)))
            sys.stderr.flush()
            return 4            # DIALOG_EXTRA
        else:
            emit_scalar(args, os.environ.get("FAKE_DIALOG_MENU_VALUE", "tag"))
            return 0

    if "--menu" in args:
        emit_scalar(args, os.environ.get("FAKE_DIALOG_MENU_VALUE", "tag"))
        return 0

    if "--yesno" in args:
        return 1            # DIALOG_CANCEL

    return 0


if __name__ == "__main__":
    sys.exit(main())
