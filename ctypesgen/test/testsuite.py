#!/usr/bin/env python3
# -*- coding: ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""Simple test suite using unittest.
By clach04 (Chris Clark).

Calling:

    python test/testsuite.py

or
    cd test
    ./testsuite.py

Could use any unitest compatible test runner (nose, etc.)

Aims to test for regressions. Where possible use stdlib to
avoid the need to compile C code.

Known to run clean with:
  * 32bit Linux (python 2.5.2, 2.6)
  * 32bit Windows XP (python 2.4, 2.5, 2.6.1)
"""

import sys
import os
import ctypes
import math
import unittest
import logging

test_directory = os.path.abspath(os.path.dirname(__file__))
sys.path.append(test_directory)
sys.path.append(os.path.join(test_directory, ".."))

import ctypesgentest  # TODO consider moving test() from ctypesgentest into this module


def cleanup_json_src_paths(json):
    """
    JSON stores the path to some source items.  These need to be genericized in
    order for tests to succeed on all machines/user accounts.
    """
    TYPES_W_PATHS = ["CtypesStruct", "CtypesEnum"]
    for i in json:
        if "ctype" in i and i["ctype"]["Klass"] in TYPES_W_PATHS:
            i["ctype"]["src"][0] = "/some-path/temp.h"


def compare_json(test_instance, json, json_ans, verbose=False):
    try:
        test_instance.assertEqual(len(json), len(json_ans))
    except:
        if verbose:
            print("JSONs do not have same length")
        raise

    # first fix paths that exist inside JSON to avoid user-specific paths:
    for i, ith_json_ans in zip(json, json_ans):
        try:
            test_instance.assertEqual(i, ith_json_ans)
        except:
            if verbose:
                print("\nFailed JSON for: ", i["name"])
                print("GENERATED:\n", i, "\nANS:\n", ith_json_ans)
            raise


class StdlibTest(unittest.TestCase):
    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = "#include <stdlib.h>\n"
        if sys.platform == "win32":
            # pick something from %windir%\system32\msvc*dll that include stdlib
            libraries = ["msvcrt.dll"]
            libraries = ["msvcrt"]
        elif sys.platform.startswith("linux"):
            libraries = ["libc.so.6"]
        else:
            libraries = ["libc"]
        self.module, output = ctypesgentest.test(header_str, libraries=libraries, all_headers=True)

    def tearDown(self):
        del self.module
        ctypesgentest.cleanup()

    def test_getenv_returns_string(self):
        """Issue 8 - Regression for crash with 64 bit and bad strings on 32 bit.
        See http://code.google.com/p/ctypesgen/issues/detail?id=8
        Test that we get a valid (non-NULL, non-empty) string back
        """
        module = self.module

        if sys.platform == "win32":
            # Check a variable that is already set
            env_var_name = (
                "USERNAME"
            )  # this is always set (as is windir, ProgramFiles, USERPROFILE, etc.)
            expect_result = os.environ[env_var_name]
            self.assertTrue(expect_result, "this should not be None or empty")
            # reason for using an existing OS variable is that unless the
            # MSVCRT dll imported is the exact same one that Python was
            # built with you can't share structures, see
            # http://msdn.microsoft.com/en-us/library/ms235460.aspx
            # "Potential Errors Passing CRT Objects Across DLL Boundaries"
        else:
            env_var_name = "HELLO"
            os.environ[env_var_name] = "WORLD"  # This doesn't work under win32
            expect_result = "WORLD"

        result = str(module.getenv(env_var_name))
        self.assertEqual(expect_result, result)

    def test_getenv_returns_null(self):
        """Related to issue 8. Test getenv of unset variable.
        """
        module = self.module
        env_var_name = "NOT SET"
        expect_result = None
        try:
            # ensure variable is not set, ignoring not set errors
            del os.environ[env_var_name]
        except KeyError:
            pass
        result = module.getenv(env_var_name)
        self.assertEqual(expect_result, result)


class StdBoolTest(unittest.TestCase):
    "Test correct parsing and generation of bool type"

    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = """
#include <stdbool.h>

struct foo
{
    bool is_bar;
    int a;
};
"""
        self.module, _ = ctypesgentest.test(header_str)  # , all_headers=True)

    def tearDown(self):
        del self.module
        ctypesgentest.cleanup()

    def test_stdbool_type(self):
        """Test is bool is correctly parsed"""
        module = self.module
        struct_foo = module.struct_foo
        self.assertEqual(struct_foo._fields_, [("is_bar", ctypes.c_bool), ("a", ctypes.c_int)])


class SimpleMacrosTest(unittest.TestCase):
    """Based on simple_macros.py
    """

    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = """
#define A 1
#define B(x,y) x+y
#define C(a,b,c) a?b:c
#define funny(x) "funny" #x
#define multipler_macro(x,y) x*y
#define minus_macro(x,y) x-y
#define divide_macro(x,y) x/y
#define mod_macro(x,y) x%y
#define subcall_macro_simple(x) (A)
#define subcall_macro_simple_plus(x) (A) + (x)
#define subcall_macro_minus(x,y) minus_macro(x,y)
#define subcall_macro_minus_plus(x,y,z) (minus_macro(x,y)) + (z)
"""
        libraries = None
        self.module, output = ctypesgentest.test(header_str)
        self.json, output = ctypesgentest.test(header_str, output_language="json")

    def _json(self, name):
        for i in self.json:
            if i["name"] == name:
                return i
        raise KeyError("Could not find JSON entry")

    def tearDown(self):
        del self.module, self.json
        ctypesgentest.cleanup()

    def test_macro_constant_int(self):
        """Tests from simple_macros.py
        """
        module, json = self.module, self._json

        self.assertEqual(module.A, 1)
        self.assertEqual(json("A"), {"name": "A", "type": "macro", "value": "1"})

    def test_macro_addition_json(self):
        json = self._json

        self.assertEqual(
            json("B"),
            {"args": ["x", "y"], "body": "(x + y)", "name": "B", "type": "macro_function"},
        )

    def test_macro_addition(self):
        """Tests from simple_macros.py
        """
        module = self.module

        self.assertEqual(module.B(2, 2), 4)

    def test_macro_ternary_json(self):
        """Tests from simple_macros.py
        """
        json = self._json

        self.assertEqual(
            json("C"),
            {
                "args": ["a", "b", "c"],
                "body": "a and b or c",
                "name": "C",
                "type": "macro_function",
            },
        )

    def test_macro_ternary_true(self):
        """Tests from simple_macros.py
        """
        module = self.module

        self.assertEqual(module.C(True, 1, 2), 1)

    def test_macro_ternary_false(self):
        """Tests from simple_macros.py
        """
        module = self.module

        self.assertEqual(module.C(False, 1, 2), 2)

    def test_macro_ternary_true_complex(self):
        """Test ?: with true, using values that can not be confused between True and 1
        """
        module = self.module

        self.assertEqual(module.C(True, 99, 100), 99)

    def test_macro_ternary_false_complex(self):
        """Test ?: with false, using values that can not be confused between True and 1
        """
        module = self.module

        self.assertEqual(module.C(False, 99, 100), 100)

    def test_macro_string_compose(self):
        """Tests from simple_macros.py
        """
        module = self.module

        self.assertEqual(module.funny("bunny"), "funnybunny")

    def test_macro_string_compose_json(self):
        """Tests from simple_macros.py
        """
        json = self._json

        self.assertEqual(
            json("funny"),
            {"args": ["x"], "body": "('funny' + x)", "name": "funny", "type": "macro_function"},
        )

    def test_macro_math_multipler(self):
        module = self.module

        x, y = 2, 5
        self.assertEqual(module.multipler_macro(x, y), x * y)

    def test_macro_math_multiplier_json(self):
        json = self._json

        self.assertEqual(
            json("multipler_macro"),
            {
                "args": ["x", "y"],
                "body": "(x * y)",
                "name": "multipler_macro",
                "type": "macro_function",
            },
        )

    def test_macro_math_minus(self):
        module = self.module

        x, y = 2, 5
        self.assertEqual(module.minus_macro(x, y), x - y)

    def test_macro_math_minus_json(self):
        json = self._json

        self.assertEqual(
            json("minus_macro"),
            {
                "args": ["x", "y"],
                "body": "(x - y)",
                "name": "minus_macro",
                "type": "macro_function",
            },
        )

    def test_macro_math_divide(self):
        module = self.module

        x, y = 2, 5
        self.assertEqual(module.divide_macro(x, y), x / y)

    def test_macro_math_divide_json(self):
        json = self._json

        self.assertEqual(
            json("divide_macro"),
            {
                "args": ["x", "y"],
                "body": "(x / y)",
                "name": "divide_macro",
                "type": "macro_function",
            },
        )

    def test_macro_math_mod(self):
        module = self.module

        x, y = 2, 5
        self.assertEqual(module.mod_macro(x, y), x % y)

    def test_macro_math_mod_json(self):
        json = self._json

        self.assertEqual(
            json("mod_macro"),
            {"args": ["x", "y"], "body": "(x % y)", "name": "mod_macro", "type": "macro_function"},
        )

    def test_macro_subcall_simple(self):
        """Test use of a constant valued macro within a macro"""
        module = self.module

        self.assertEqual(module.subcall_macro_simple(2), 1)

    def test_macro_subcall_simple_json(self):
        json = self._json

        self.assertEqual(
            json("subcall_macro_simple"),
            {"args": ["x"], "body": "A", "name": "subcall_macro_simple", "type": "macro_function"},
        )

    def test_macro_subcall_simple_plus(self):
        """Test math with constant valued macro within a macro"""
        module = self.module

        self.assertEqual(module.subcall_macro_simple_plus(2), 1 + 2)

    def test_macro_subcall_simple_plus_json(self):
        json = self._json

        self.assertEqual(
            json("subcall_macro_simple_plus"),
            {
                "args": ["x"],
                "body": "(A + x)",
                "name": "subcall_macro_simple_plus",
                "type": "macro_function",
            },
        )

    def test_macro_subcall_minus(self):
        """Test use of macro function within a macro"""
        module = self.module

        x, y = 2, 5
        self.assertEqual(module.subcall_macro_minus(x, y), x - y)

    def test_macro_subcall_minus_json(self):
        json = self._json

        self.assertEqual(
            json("subcall_macro_minus"),
            {
                "args": ["x", "y"],
                "body": "(minus_macro (x, y))",
                "name": "subcall_macro_minus",
                "type": "macro_function",
            },
        )

    def test_macro_subcall_minus_plus(self):
        """Test math with a macro function within a macro"""
        module = self.module

        x, y, z = 2, 5, 1
        self.assertEqual(module.subcall_macro_minus_plus(x, y, z), (x - y) + z)

    def test_macro_subcall_minus_plus_json(self):
        json = self._json

        self.assertEqual(
            json("subcall_macro_minus_plus"),
            {
                "args": ["x", "y", "z"],
                "body": "((minus_macro (x, y)) + z)",
                "name": "subcall_macro_minus_plus",
                "type": "macro_function",
            },
        )


class StructuresTest(unittest.TestCase):
    """Based on structures.py
    """

    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.

        NOTE:  Very possibly, if you change this header string, you need to change the line
               numbers in the JSON output test result below (in
               test_struct_json).
        """
        header_str = """

struct foo
{
        int a;
        char b;
        int c;
        int d : 15;
        int   : 17;
};

struct __attribute__((packed)) packed_foo
{
        int a;
        char b;
        int c;
        int d : 15;
        int   : 17;
};

typedef struct
{
        int a;
        char b;
        int c;
        int d : 15;
        int   : 17;
} foo_t;

typedef struct __attribute__((packed))
{
        int a;
        char b;
        int c;
        int d : 15;
        int   : 17;
} packed_foo_t;

typedef int Int;

typedef struct {
        int Int;
} id_struct_t;
"""
        libraries = None
        self.module, output = ctypesgentest.test(header_str)
        self.json, output = ctypesgentest.test(header_str, output_language="json")
        cleanup_json_src_paths(self.json)

    def tearDown(self):
        del self.module
        ctypesgentest.cleanup()

    def test_struct_json(self):
        json_ans = [
            {
                "fields": [
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "a",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "char",
                            "signed": True,
                        },
                        "name": "b",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "c",
                    },
                    {
                        "bitfield": "15",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 15,
                            },
                            "errors": [],
                        },
                        "name": "d",
                    },
                    {
                        "bitfield": "17",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 17,
                            },
                            "errors": [],
                        },
                        "name": None,
                    },
                ],
                "name": "foo",
                "type": "struct",
            },
            {
                "fields": [
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "a",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "char",
                            "signed": True,
                        },
                        "name": "b",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "c",
                    },
                    {
                        "bitfield": "15",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 15,
                            },
                            "errors": [],
                        },
                        "name": "d",
                    },
                    {
                        "bitfield": "17",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 17,
                            },
                            "errors": [],
                        },
                        "name": None,
                    },
                ],
                "name": "packed_foo",
                "type": "struct",
            },
            {
                "fields": [
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "a",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "char",
                            "signed": True,
                        },
                        "name": "b",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "c",
                    },
                    {
                        "bitfield": "15",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 15,
                            },
                            "errors": [],
                        },
                        "name": "d",
                    },
                    {
                        "bitfield": "17",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 17,
                            },
                            "errors": [],
                        },
                        "name": None,
                    },
                ],
                "name": "anon_4",
                "type": "struct",
            },
            {
                "ctype": {
                    "Klass": "CtypesStruct",
                    "anonymous": True,
                    "errors": [],
                    "members": [
                        [
                            "a",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "b",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "char",
                                "signed": True,
                            },
                        ],
                        [
                            "c",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "d",
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 15,
                                },
                                "errors": [],
                            },
                        ],
                        [
                            None,
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 17,
                                },
                                "errors": [],
                            },
                        ],
                    ],
                    "opaque": False,
                    "packed": False,
                    "src": ["/some-path/temp.h", 21],
                    "tag": "anon_4",
                    "variety": "struct",
                },
                "name": "foo_t",
                "type": "typedef",
            },
            {
                "fields": [
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "a",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "char",
                            "signed": True,
                        },
                        "name": "b",
                    },
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "c",
                    },
                    {
                        "bitfield": "15",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 15,
                            },
                            "errors": [],
                        },
                        "name": "d",
                    },
                    {
                        "bitfield": "17",
                        "ctype": {
                            "Klass": "CtypesBitfield",
                            "base": {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                            "bitfield": {
                                "Klass": "ConstantExpressionNode",
                                "errors": [],
                                "value": 17,
                            },
                            "errors": [],
                        },
                        "name": None,
                    },
                ],
                "name": "anon_5",
                "type": "struct",
            },
            {
                "ctype": {
                    "Klass": "CtypesStruct",
                    "anonymous": True,
                    "errors": [],
                    "members": [
                        [
                            "a",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "b",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "char",
                                "signed": True,
                            },
                        ],
                        [
                            "c",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "d",
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 15,
                                },
                                "errors": [],
                            },
                        ],
                        [
                            None,
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 17,
                                },
                                "errors": [],
                            },
                        ],
                    ],
                    "opaque": False,
                    "packed": True,
                    "src": ["/some-path/temp.h", 30],
                    "tag": "anon_5",
                    "variety": "struct",
                },
                "name": "packed_foo_t",
                "type": "typedef",
            },
            {
                "ctype": {
                    "Klass": "CtypesSimple",
                    "errors": [],
                    "longs": 0,
                    "name": "int",
                    "signed": True,
                },
                "name": "Int",
                "type": "typedef",
            },
            {
                "fields": [
                    {
                        "ctype": {
                            "Klass": "CtypesSimple",
                            "errors": [],
                            "longs": 0,
                            "name": "int",
                            "signed": True,
                        },
                        "name": "Int",
                    }
                ],
                "name": "anon_6",
                "type": "struct",
            },
            {
                "ctype": {
                    "Klass": "CtypesStruct",
                    "anonymous": True,
                    "errors": [],
                    "members": [
                        [
                            "Int",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ]
                    ],
                    "opaque": False,
                    "packed": False,
                    "src": ["/some-path/temp.h", 41],
                    "tag": "anon_6",
                    "variety": "struct",
                },
                "name": "id_struct_t",
                "type": "typedef",
            },
            {
                "ctype": {
                    "Klass": "CtypesStruct",
                    "anonymous": False,
                    "errors": [],
                    "members": [
                        [
                            "a",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "b",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "char",
                                "signed": True,
                            },
                        ],
                        [
                            "c",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "d",
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 15,
                                },
                                "errors": [],
                            },
                        ],
                        [
                            None,
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 17,
                                },
                                "errors": [],
                            },
                        ],
                    ],
                    "opaque": False,
                    "packed": False,
                    "src": ["/some-path/temp.h", 3],
                    "tag": "foo",
                    "variety": "struct",
                },
                "name": "foo",
                "type": "typedef",
            },
            {
                "ctype": {
                    "Klass": "CtypesStruct",
                    "anonymous": False,
                    "errors": [],
                    "members": [
                        [
                            "a",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "b",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "char",
                                "signed": True,
                            },
                        ],
                        [
                            "c",
                            {
                                "Klass": "CtypesSimple",
                                "errors": [],
                                "longs": 0,
                                "name": "int",
                                "signed": True,
                            },
                        ],
                        [
                            "d",
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 15,
                                },
                                "errors": [],
                            },
                        ],
                        [
                            None,
                            {
                                "Klass": "CtypesBitfield",
                                "base": {
                                    "Klass": "CtypesSimple",
                                    "errors": [],
                                    "longs": 0,
                                    "name": "int",
                                    "signed": True,
                                },
                                "bitfield": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 17,
                                },
                                "errors": [],
                            },
                        ],
                    ],
                    "opaque": False,
                    "packed": True,
                    "src": ["/some-path/temp.h", 12],
                    "tag": "packed_foo",
                    "variety": "struct",
                },
                "name": "packed_foo",
                "type": "typedef",
            },
        ]

        compare_json(self, self.json, json_ans)

    def test_fields(self):
        """Test whether fields are built correctly.
        """
        struct_foo = self.module.struct_foo
        self.assertEqual(
            struct_foo._fields_,
            [
                ("a", ctypes.c_int),
                ("b", ctypes.c_char),
                ("c", ctypes.c_int),
                ("d", ctypes.c_int, 15),
                ("unnamed_1", ctypes.c_int, 17),
            ],
        )

    def test_pack(self):
        """Test whether gcc __attribute__((packed)) is interpreted correctly.
        """
        unpacked_size = ctypes.sizeof(ctypes.c_int) * 4
        packed_size = ctypes.sizeof(ctypes.c_int) * 3 + ctypes.sizeof(ctypes.c_char)

        struct_foo = self.module.struct_foo
        struct_packed_foo = self.module.struct_packed_foo
        foo_t = self.module.foo_t
        packed_foo_t = self.module.packed_foo_t
        self.assertEqual(getattr(struct_foo, "_pack_", 0), 0)
        self.assertEqual(getattr(struct_packed_foo, "_pack_", 0), 1)
        self.assertEqual(getattr(foo_t, "_pack_", 0), 0)
        self.assertEqual(getattr(packed_foo_t, "_pack_", -1), 1)
        self.assertEqual(ctypes.sizeof(struct_foo), unpacked_size)
        self.assertEqual(ctypes.sizeof(foo_t), unpacked_size)
        self.assertEqual(ctypes.sizeof(struct_packed_foo), packed_size)
        self.assertEqual(ctypes.sizeof(packed_foo_t), packed_size)

    def test_typedef_vs_field_id(self):
        """Test whether local field identifier names can override external
        typedef names.
        """
        Int = self.module.Int
        id_struct_t = self.module.id_struct_t
        self.assertEqual(Int, ctypes.c_int)
        self.assertEqual(id_struct_t._fields_, [("Int", ctypes.c_int)])


class MathTest(unittest.TestCase):
    """Based on math_functions.py"""

    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = """
#include <math.h>
#define sin_plus_y(x,y) (sin(x) + (y))
"""
        if sys.platform == "win32":
            # pick something from %windir%\system32\msvc*dll that include stdlib
            libraries = ["msvcrt.dll"]
            libraries = ["msvcrt"]
        elif sys.platform.startswith("linux"):
            libraries = ["libm.so.6"]
        else:
            libraries = ["libc"]
        self.module, output = ctypesgentest.test(header_str, libraries=libraries, all_headers=True)

    def tearDown(self):
        del self.module
        ctypesgentest.cleanup()

    def test_sin(self):
        """Based on math_functions.py"""
        module = self.module

        self.assertEqual(module.sin(2), math.sin(2))

    def test_sqrt(self):
        """Based on math_functions.py"""
        module = self.module

        self.assertEqual(module.sqrt(4), 2)

        def local_test():
            module.sin("foobar")

        self.assertRaises(ctypes.ArgumentError, local_test)

    def test_bad_args_string_not_number(self):
        """Based on math_functions.py"""
        module = self.module

        def local_test():
            module.sin("foobar")

        self.assertRaises(ctypes.ArgumentError, local_test)

    def test_subcall_sin(self):
        """Test math with sin(x) in a macro"""
        module = self.module

        self.assertEqual(module.sin_plus_y(2, 1), math.sin(2) + 1)


class EnumTest(unittest.TestCase):
    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = """
        typedef enum {
            TEST_1 = 0,
            TEST_2
        } test_status_t;
        """
        libraries = None
        self.module, output = ctypesgentest.test(header_str)
        self.json, output = ctypesgentest.test(header_str, output_language="json")
        cleanup_json_src_paths(self.json)

    def tearDown(self):
        del self.module, self.json
        ctypesgentest.cleanup()

    def test_enum(self):
        self.assertEqual(self.module.TEST_1, 0)
        self.assertEqual(self.module.TEST_2, 1)

    def test_enum_json(self):
        json_ans = [
            {
                "fields": [
                    {
                        "ctype": {"Klass": "ConstantExpressionNode", "errors": [], "value": 0},
                        "name": "TEST_1",
                    },
                    {
                        "ctype": {
                            "Klass": "BinaryExpressionNode",
                            "can_be_ctype": [False, False],
                            "errors": [],
                            "format": "(%s + %s)",
                            "left": {
                                "Klass": "IdentifierExpressionNode",
                                "errors": [],
                                "name": "TEST_1",
                            },
                            "name": "addition",
                            "right": {"Klass": "ConstantExpressionNode", "errors": [], "value": 1},
                        },
                        "name": "TEST_2",
                    },
                ],
                "name": "anon_2",
                "type": "enum",
            },
            {"name": "TEST_1", "type": "constant", "value": "0"},
            {"name": "TEST_2", "type": "constant", "value": "(TEST_1 + 1)"},
            {
                "ctype": {
                    "Klass": "CtypesEnum",
                    "anonymous": True,
                    "enumerators": [
                        ["TEST_1", {"Klass": "ConstantExpressionNode", "errors": [], "value": 0}],
                        [
                            "TEST_2",
                            {
                                "Klass": "BinaryExpressionNode",
                                "can_be_ctype": [False, False],
                                "errors": [],
                                "format": "(%s + %s)",
                                "left": {
                                    "Klass": "IdentifierExpressionNode",
                                    "errors": [],
                                    "name": "TEST_1",
                                },
                                "name": "addition",
                                "right": {
                                    "Klass": "ConstantExpressionNode",
                                    "errors": [],
                                    "value": 1,
                                },
                            },
                        ],
                    ],
                    "errors": [],
                    "opaque": False,
                    "src": ["/some-path/temp.h", 2],
                    "tag": "anon_2",
                },
                "name": "test_status_t",
                "type": "typedef",
            },
        ]

        compare_json(self, self.json, json_ans)


class PrototypeTest(unittest.TestCase):
    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = """
        int bar2(int a);
        int bar(int);
        void foo(void);
        """
        libraries = None
        self.json, output = ctypesgentest.test(header_str, output_language="json")
        cleanup_json_src_paths(self.json)

    def tearDown(self):
        del self.json
        ctypesgentest.cleanup()

    def test_function_prototypes_json(self):
        json_ans = [
            {
                "args": [
                    {
                        "Klass": "CtypesSimple",
                        "errors": [],
                        "identifier": "a",
                        "longs": 0,
                        "name": "int",
                        "signed": True,
                    }
                ],
                "name": "bar2",
                "return": {
                    "Klass": "CtypesSimple",
                    "errors": [],
                    "longs": 0,
                    "name": "int",
                    "signed": True,
                },
                "type": "function",
                "variadic": False,
            },
            {
                "args": [
                    {
                        "Klass": "CtypesSimple",
                        "errors": [],
                        "identifier": "",
                        "longs": 0,
                        "name": "int",
                        "signed": True,
                    }
                ],
                "name": "bar",
                "return": {
                    "Klass": "CtypesSimple",
                    "errors": [],
                    "longs": 0,
                    "name": "int",
                    "signed": True,
                },
                "type": "function",
                "variadic": False,
            },
            {
                "args": [],
                "name": "foo",
                "return": {
                    "Klass": "CtypesSimple",
                    "errors": [],
                    "longs": 0,
                    "name": "void",
                    "signed": True,
                },
                "type": "function",
                "variadic": False,
            },
        ]

        compare_json(self, self.json, json_ans, True)


class LongDoubleTest(unittest.TestCase):
    "Test correct parsing and generation of 'long double' type"

    def setUp(self):
        """NOTE this is called once for each test* method
        (it is not called once per class).
        FIXME This is slightly inefficient as it is called *way* more times than it needs to be.
        """
        header_str = """
        struct foo
        {
            long double is_bar;
            int a;
        };
        """
        self.module, _ = ctypesgentest.test(header_str)  # , all_headers=True)

    def tearDown(self):
        del self.module
        ctypesgentest.cleanup()

    def test_longdouble_type(self):
        """Test is long double is correctly parsed"""
        module = self.module
        struct_foo = module.struct_foo
        self.assertEqual(
            struct_foo._fields_, [("is_bar", ctypes.c_longdouble), ("a", ctypes.c_int)]
        )


def main(argv=None):
    if argv is None:
        argv = sys.argv

    ctypesgentest.ctypesgen.messages.log.setLevel(logging.CRITICAL)  # do not log anything
    unittest.main()

    return 0


if __name__ == "__main__":
    sys.exit(main())
