# -*- coding: utf-8 -*-
"""Unit and integration tests for dialog.py.

Run with::

    python3 -m unittest discover -s tests -v

No third-party test framework is required.
"""

import os
import pathlib
import tempfile
import unittest
import warnings
from unittest import mock

import dialog


HERE = pathlib.Path(__file__).resolve().parent
FAKE_DIALOG = HERE / "fake_dialog.py"


class TestVersionInfo(unittest.TestCase):
    def test_str_and_repr(self):
        self.assertEqual(str(dialog.version_info), "3.7.0")
        self.assertEqual(dialog.__version__, "3.7.0")
        self.assertIn("VersionInfo", repr(dialog.version_info))

    def test_release_suffix(self):
        info = dialog.VersionInfo(1, 2, 3, ".rc1")
        self.assertEqual(str(info), "1.2.3.rc1")


class TestBackendVersion(unittest.TestCase):
    def test_fromstring_and_str(self):
        version = dialog.DialogBackendVersion.fromstring("1.2-20130902")
        self.assertEqual(str(version), "1.2-20130902")
        self.assertEqual(version.dotted_part, [1, 2])
        self.assertEqual(version.rest, "-20130902")

    def test_constructor_accepts_string(self):
        self.assertEqual(dialog.DialogBackendVersion("1.2-20130902"),
                         dialog.DialogBackendVersion([1, 2], "-20130902"))

    def test_ordering(self):
        versions = ["1.2", "1.2-20130902", "1.2-20130903", "1.2.0",
                    "1.2.0-20130902"]
        parsed = [dialog.DialogBackendVersion.fromstring(v) for v in versions]
        self.assertEqual(parsed, sorted(parsed))

    def test_invalid_version(self):
        with self.assertRaises(dialog.UnableToParseDialogBackendVersion):
            dialog.DialogBackendVersion.fromstring("not-a-version")

    def test_invalid_dotted_part(self):
        with self.assertRaises(dialog.BadPythonDialogUsage):
            dialog.DialogBackendVersion([1, "two"])

    def test_generator_dotted_part(self):
        # A generator must not be consumed by the validation loop.
        version = dialog.DialogBackendVersion(x for x in (1, 2))
        self.assertEqual(version.dotted_part, [1, 2])


class TestHelpers(unittest.TestCase):
    def setUp(self):
        self.d = dialog.Dialog.__new__(dialog.Dialog)

    def test_dash_escape(self):
        self.assertEqual(
            dialog._dash_escape(["--a", "b", "--c"]),
            ["--", "--a", "b", "--", "--c"])
        self.assertEqual(
            dialog._dash_escape_nf(["--a", "--b"]),
            ["--a", "--", "--b"])

    def test_to_onoff(self):
        for value in (True, 1, "on", "ON", "oN"):
            self.assertEqual(dialog._to_onoff(value), "on")
        for value in (False, 0, "off", "OFF"):
            self.assertEqual(dialog._to_onoff(value), "off")
        with self.assertRaises(dialog.BadPythonDialogUsage):
            dialog._to_onoff("maybe")

    def test_split_shellstyle_arglist(self):
        parse = self.d._split_shellstyle_arglist
        self.assertEqual(parse("a b c"), ["a", "b", "c"])
        self.assertEqual(parse('"a b" c'), ["a b", "c"])
        self.assertEqual(parse('"a\\"b" c'), ['a"b', "c"])

    def test_parse_quoted_string(self):
        parse = self.d._parse_quoted_string
        self.assertEqual(parse('"abc" rest'), ("abc", 5))
        self.assertEqual(parse('"a\\"b" rest'), ('a"b', 6))

    def test_parse_quoted_string_unterminated(self):
        with self.assertRaises(dialog.PythonDialogBug):
            self.d._parse_quoted_string('"abc')


class TestCommonArgs(unittest.TestCase):
    def test_representative_options(self):
        self.assertEqual(dialog._compute_common_args({"title": "Hi"}),
                         ["--title", "Hi"])
        self.assertEqual(dialog._compute_common_args({"no_shadow": True}),
                         ["--no-shadow"])
        self.assertEqual(dialog._compute_common_args({"no_shadow": False}), [])
        self.assertEqual(dialog._compute_common_args({"begin": (2, 4)}),
                         ["--begin", "2", "4"])

    def test_new_options(self):
        cases = {
            "color_mode": (2, ["--color-mode", "2"]),
            "cursor_off_label": (True, ["--cursor-off-label"]),
            "erase_on_exit": (True, ["--erase-on-exit"]),
            "input_fd": (3, ["--input-fd", "3"]),
            "iso_week": (True, ["--iso-week"]),
            "no_hot_list": (True, ["--no-hot-list"]),
            "output_fd": (4, ["--output-fd", "4"]),
            "output_separator": (";", ["--output-separator", ";"]),
            "separator": ("|", ["--output-separator", "|"]),
            "quoted": (True, ["--quoted"]),
            "single_quoted": (True, ["--single-quoted"]),
            "reorder": (True, ["--reorder"]),
        }
        for name, (value, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    dialog._compute_common_args({name: value}), expected)

    def test_unknown_option(self):
        with self.assertRaises(dialog.BadPythonDialogUsage):
            dialog._compute_common_args({"not_an_option": True})


class TestParseHelp(unittest.TestCase):
    def setUp(self):
        # _parse_help() only uses _help_status_on(), which doesn't need a
        # fully initialized Dialog instance.
        self.d = dialog.Dialog.__new__(dialog.Dialog)
        self.d.dialog_persistent_arglist = []

    def test_simple_help(self):
        self.assertEqual(self.d._parse_help("HELP tag\n", {}), "tag")

    def test_help_status(self):
        self.assertEqual(
            self.d._parse_help("HELP tag status\n", {"help_status": True}),
            ("tag", "status"))

    def test_help_status_multival(self):
        self.assertEqual(
            self.d._parse_help("HELP tag\na\nb\n",
                               {"help_status": True}, multival=True),
            ("tag", ["a", "b"]))

    def test_raw_help(self):
        self.assertEqual(
            self.d._parse_help("raw value\n", {}, raw_format=True),
            "raw value")

    def test_empty_help_with_help_status(self):
        with self.assertRaises(dialog.PythonDialogBug):
            self.d._parse_help("", {"help_status": True})

    def test_help_status_output_separator(self):
        self.assertEqual(
            self.d._parse_help(
                "HELP tag;sel1;sel2;",
                {"help_status": True, "output_separator": ";"},
                multival=True, default_separator="\n", strip_trailing=True),
            ("tag", ["sel1", "sel2"]))

    def test_help_status_quoted(self):
        self.assertEqual(
            self.d._parse_help(
                'HELP "help id" "sel 1" "sel 2"',
                {"help_status": True, "quoted": True},
                multival=True, default_separator=" ", always_quoted=True),
            ("help id", ["sel 1", "sel 2"]))

    def test_help_status_single_quoted(self):
        self.assertEqual(
            self.d._parse_help(
                "HELP 'help id' 'sel 1' 'sel 2'",
                {"help_status": True, "single_quoted": True},
                multival=True, default_separator=" ", always_quoted=True),
            ("help id", ["sel 1", "sel 2"]))

    def test_help_single_value_quoted(self):
        self.assertEqual(
            self.d._parse_help(
                'HELP "tag with space" "status text"',
                {"help_status": True, "quoted": True},
                default_separator=" ", always_quoted=True),
            ("tag with space", "status text"))

    def test_split_fields(self):
        self.assertEqual(
            self.d._split_fields('"a b" "c d"', " ", '"'),
            ["a b", "c d"])
        self.assertEqual(self.d._split_fields("a,b,c", ",", '"'),
                         ["a", "b", "c"])
        self.assertEqual(self.d._split_fields('"a,b",c', ",", '"'),
                         ["a,b", "c"])
        self.assertEqual(self.d._split_fields('"a\\"b",c', ",", '"'),
                         ['a"b', "c"])

    def test_unquote_string(self):
        self.assertEqual(
            self.d._unquote_string('"a b"', {"quoted": True}), "a b")
        self.assertEqual(
            self.d._unquote_string(
                "'a b'", {"quoted": True, "single_quoted": True}), "a b")
        # --single-quoted alone does not enable quoting.
        self.assertEqual(
            self.d._unquote_string("'a b'", {"single_quoted": True}),
            "'a b'")
        # Without the option, quotes are literal.
        self.assertEqual(self.d._unquote_string('"a b"', {}), '"a b"')


class TestFakeBackend(unittest.TestCase):
    def make_dialog(self, **kwargs):
        return dialog.Dialog(dialog=str(FAKE_DIALOG), **kwargs)

    def test_backend_version_and_maxsize(self):
        d = self.make_dialog()
        self.assertEqual(d.backend_version(), "1.3-20250817")
        self.assertEqual(str(d.cached_backend_version), "1.3-20250817")
        self.assertEqual(d.maxsize(), (24, 80))

    def test_basic_widgets_direct_args(self):
        d = self.make_dialog(pass_args_via_file=False)
        self.assertEqual(d.msgbox("hi"), dialog.Dialog.OK)
        self.assertEqual(d.yesno("?"), dialog.Dialog.CANCEL)
        self.assertEqual(d.inputbox("?"), (dialog.Dialog.OK, "hello"))

    def test_basic_widgets_via_file(self):
        d = self.make_dialog(pass_args_via_file=True)
        self.assertEqual(d.inputbox("?"), (dialog.Dialog.OK, "hello"))
        self.assertEqual(
            d.rangebox("?", min=0, max=100, init=50),
            (dialog.Dialog.OK, 42))
        self.assertEqual(
            d.checklist("?", choices=[("tag1", "item1", True),
                                      ("tag2", "item2", False)]),
            (dialog.Dialog.OK, ["tag1", "tag2"]))

    def test_new_widgets(self):
        d = self.make_dialog()
        self.assertEqual(d.prgbox("echo hi"), dialog.Dialog.OK)
        self.assertEqual(d.prgbox("echo hi", 10, 40), dialog.Dialog.OK)
        self.assertEqual(d.prgbox("caption", "echo hi", 10, 40),
                         dialog.Dialog.OK)
        self.assertEqual(d.tailboxbg("/tmp/file", no_kill=True),
                         (dialog.Dialog.OK, 12345))
        self.assertEqual(d.tailboxbg("/tmp/file"), (dialog.Dialog.OK, None))

    def test_prgbox_validation(self):
        d = self.make_dialog()
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d.prgbox(123)
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d.prgbox(123, "echo hi")

    def test_gauge(self):
        d = self.make_dialog()
        d.gauge_start(text="working", percent=0)
        d.gauge_update(50)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            d.gauge_iterate(75)
        self.assertEqual(d.gauge_stop(), dialog.Dialog.OK)

    def test_dialog_error(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ, {"FAKE_DIALOG_ERROR": "1"}):
            with self.assertRaises(dialog.DialogError):
                d.msgbox("hi")

    def test_help_output(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ, {"FAKE_DIALOG_HELP": "1"}):
            self.assertEqual(d.menu("?", choices=[("tag", "item")]),
                             (dialog.Dialog.HELP, "tag"))
            # editbox help output is raw text, not a "HELP ..." record.
            self.assertEqual(d.editbox("/tmp/file"),
                             (dialog.Dialog.HELP, "HELP tag"))

    def test_unexpected_rangebox_output(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ, {"FAKE_DIALOG_OUTPUT": "not-int"}):
            with self.assertRaises(dialog.UnexpectedDialogOutput):
                d.rangebox("?", min=0, max=10, init=5)


class TestOutputOptions(unittest.TestCase):
    def make_dialog(self):
        return dialog.Dialog(dialog=str(FAKE_DIALOG),
                             pass_args_via_file=False)

    def test_checklist_output_separator(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag 1,tag 2"}):
            self.assertEqual(
                d.checklist(
                    "?", choices=[("tag 1", "item", True),
                                  ("tag 2", "item", False)],
                    output_separator=";"),
                (dialog.Dialog.OK, ["tag 1", "tag 2"]))

    def test_checklist_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag 1,tag 2"}):
            self.assertEqual(
                d.checklist(
                    "?", choices=[("tag 1", "item", True),
                                  ("tag 2", "item", False)],
                    output_separator=";", quoted=True),
                (dialog.Dialog.OK, ["tag 1", "tag 2"]))

    def test_checklist_single_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag 1,tag 2"}):
            self.assertEqual(
                d.checklist(
                    "?", choices=[("tag 1", "item", True),
                                  ("tag 2", "item", False)],
                    output_separator=";", quoted=True, single_quoted=True),
                (dialog.Dialog.OK, ["tag 1", "tag 2"]))

    def test_buildlist_default_quoting(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag 1,tag 2"}):
            self.assertEqual(
                d.buildlist("?", items=[("tag 1", "item", True),
                                        ("tag 2", "item", False)]),
                (dialog.Dialog.OK, ["tag 1", "tag 2"]))

    def test_buildlist_single_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag 1,tag 2"}):
            self.assertEqual(
                d.buildlist("?", items=[("tag 1", "item", True),
                                        ("tag 2", "item", False)],
                            single_quoted=True),
                (dialog.Dialog.OK, ["tag 1", "tag 2"]))

    def test_buildlist_custom_separator(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag 1,tag 2"}):
            self.assertEqual(
                d.buildlist("?", items=[("tag 1", "item", True),
                                        ("tag 2", "item", False)],
                            output_separator=",", quoted=True),
                (dialog.Dialog.OK, ["tag 1", "tag 2"]))

    def test_form_quoted(self):
        d = self.make_dialog()
        elements = [("Label1", 1, 1, "v1", 1, 10, 10, 10),
                    ("Label2", 2, 1, "v2", 2, 10, 10, 10)]
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_FORM_VALUES": "value 1,value 2"}):
            self.assertEqual(
                d.form("?", elements=elements, quoted=True),
                (dialog.Dialog.OK, ["value 1", "value 2"]))

    def test_editbox_output_separator(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_EDITBOX_LINES": "line 1,line 2"}):
            self.assertEqual(
                d.editbox("/tmp/file", output_separator="|"),
                (dialog.Dialog.OK, "line 1\nline 2\n"))

    def test_menu_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_MENU_VALUE": "tag with space"}):
            self.assertEqual(
                d.menu("?", choices=[("tag with space", "item")],
                       quoted=True),
                (dialog.Dialog.OK, "tag with space"))

    def test_inputbox_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_INPUT": "hello world"}):
            self.assertEqual(d.inputbox("?", quoted=True),
                             (dialog.Dialog.OK, "hello world"))

    def test_radiolist_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag with space"}):
            self.assertEqual(
                d.radiolist("?", choices=[("tag with space", "item", True)],
                            quoted=True),
                (dialog.Dialog.OK, "tag with space"))

    def test_treeview_quoted(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ,
                             {"FAKE_DIALOG_LIST_VALUES": "tag with space"}):
            self.assertEqual(
                d.treeview("?", nodes=[("tag with space", "item", True, 0)],
                           quoted=True),
                (dialog.Dialog.OK, "tag with space"))

    def test_inputmenu_renamed_quoted(self):
        d = self.make_dialog()
        env = {"FAKE_DIALOG_INPUTMENU_RENAMED": "1",
               "FAKE_DIALOG_INPUTMENU_TAG": "tag 1",
               "FAKE_DIALOG_INPUTMENU_ITEM": "new item"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(
                d.inputmenu("?", choices=[("tag 1", "item")], quoted=True),
                ("renamed", "tag 1", "new item"))


class TestChain(unittest.TestCase):
    def make_dialog(self, **kwargs):
        kwargs.setdefault("pass_args_via_file", False)
        return dialog.Dialog(dialog=str(FAKE_DIALOG), **kwargs)

    def test_arguments(self):
        d = self.make_dialog()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "argv")
            with mock.patch.dict(os.environ,
                                 {"FAKE_DIALOG_ARGV_FILE": path}):
                d.perform_chain([
                    (["--inputbox", "Name:", "10", "40"], {"title": "One"}),
                    (["--menu", "Choose:", "10", "40", "2", "tag", "item"],
                     {"title": "Two"}),
                ])
            with open(path, encoding="utf-8") as f:
                args = f.read().splitlines()

        self.assertIn("--and-widget", args)
        self.assertIn("--separate-widget", args)
        self.assertIn("One", args)
        self.assertIn("Two", args)
        self.assertLess(args.index("--separate-widget"),
                        args.index("--inputbox"))
        self.assertLess(args.index("--inputbox"),
                        args.index("--and-widget"))
        self.assertLess(args.index("--and-widget"),
                        args.index("--menu"))

    def test_two_widgets(self):
        d = self.make_dialog()
        code, segments = d.perform_chain([
            (["--inputbox", "Name:", "10", "40"], {}),
            (["--menu", "Choose:", "10", "40", "2", "tag", "item"], {}),
        ])
        self.assertEqual((code, segments),
                         (dialog.Dialog.OK, ["hello", "tag"]))

    def test_two_widgets_via_file(self):
        d = self.make_dialog(pass_args_via_file=True)
        code, segments = d.perform_chain([
            (["--inputbox", "Name:", "10", "40"], {}),
            (["--menu", "Choose:", "10", "40", "2", "tag", "item"], {}),
        ])
        self.assertEqual((code, segments),
                         (dialog.Dialog.OK, ["hello", "tag"]))

    def test_cancel_continues_and_last_code(self):
        d = self.make_dialog()
        code, segments = d.perform_chain([
            (["--inputbox", "Name:", "10", "40"], {}),
            (["--menu", "Choose:", "10", "40", "2", "tag", "item"], {}),
            (["--yesno", "Again?", "10", "40"], {}),
        ])
        self.assertEqual((code, segments),
                         (dialog.Dialog.CANCEL, ["hello", "tag"]))

    def test_esc_stops(self):
        d = self.make_dialog()
        with mock.patch.dict(os.environ, {"FAKE_DIALOG_ESC": "1"}):
            code, segments = d.perform_chain([
                (["--inputbox", "Name:", "10", "40"], {}),
                (["--menu", "Choose:", "10", "40", "2", "tag", "item"], {}),
                (["--inputbox", "After:", "10", "40"], {}),
            ])
        self.assertEqual((code, segments),
                         (dialog.Dialog.ESC, ["hello"]))

    def test_custom_separator(self):
        d = self.make_dialog()
        code, segments = d.perform_chain([
            (["--inputbox", "Name:", "10", "40"], {}),
            (["--menu", "Choose:", "10", "40", "2", "tag", "item"], {}),
        ], separator="|")
        self.assertEqual((code, segments),
                         (dialog.Dialog.OK, ["hello", "tag"]))

    def test_empty(self):
        d = self.make_dialog()
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d.perform_chain([])

    def test_rejects_separate_output(self):
        d = self.make_dialog()
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d.perform_chain([
                (["--msgbox", "x", "10", "40"],
                 {"separate_output": True})])

    def test_rejects_separate_widget(self):
        d = self.make_dialog()
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d.perform_chain([
                (["--msgbox", "x", "10", "40"],
                 {"separate_widget": "|"})])

    def test_rejects_and_widget_in_args(self):
        d = self.make_dialog()
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d.perform_chain([
                (["--and-widget", "--msgbox", "x", "10", "40"], {})])


class TestUsageErrors(unittest.TestCase):
    def test_invalid_compat(self):
        with self.assertRaises(dialog.BadPythonDialogUsage):
            dialog.Dialog(dialog=str(FAKE_DIALOG), compat="something")

    def test_missing_executable(self):
        with self.assertRaises(dialog.ExecutableNotFound):
            dialog.Dialog(dialog="/nonexistent/dialog")

    def test_progressbox_requires_exactly_one_source(self):
        d = dialog.Dialog.__new__(dialog.Dialog)
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d._progressboxoid("progressbox")
        with self.assertRaises(dialog.BadPythonDialogUsage):
            d._progressboxoid("progressbox", file_path="/tmp/x", fd=3)


class TestExceptionHierarchy(unittest.TestCase):
    def test_hierarchy(self):
        self.assertTrue(issubclass(dialog.PythonDialogIOError,
                                   dialog.PythonDialogOSError))
        self.assertTrue(issubclass(dialog.PythonDialogOSError,
                                   dialog.PythonDialogSystemError))
        self.assertTrue(issubclass(dialog.PythonDialogSystemError,
                                   dialog.error))
        self.assertIs(dialog.PythonDialogException, dialog.error)


if __name__ == "__main__":
    unittest.main()
