#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright 2022 The SVUT Authors

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# pylint: disable=W0621

import os
import sys
import argparse
import filecmp
import subprocess
import datetime
from timeit import default_timer as timer
from datetime import timedelta

SCRIPTDIR = os.path.abspath(os.path.dirname(__file__))


def check_arguments(args):
    """
    Verify the arguments are correctly setup
    """

    if "iverilog" in args.simulator or "icarus" in args.simulator:
        print_event("Run with Icarus Verilog")
    elif "verilator" in args.simulator:
        print_event("Run with Verilator")
    else:
        print_event("ERROR: Simulator not supported")
        sys.exit(1)

    if args.test == "":
        print_event("ERROR: No testcase passed")
        sys.exit(1)

    if args.compile_only and args.run_only:
        print("ERROR: Both compile-only and run-only are used")
        sys.exit(1)

    if (args.compile_only or args.run_only) and args.test=="all":
        print_event("ERROR: compile-only or run-only can't be used with multiple testbenchs")
        sys.exit(1)

    return 0


def check_tb_extension(test):
    """
    Check the extension to be sure it can be run
    """
    if test[-2:] != ".v" and test[-3:] != ".sv":
        print("ERROR: Failed to find supported extension. Must use either *.v or *.sv")
        sys.exit(1)


def copy_svut_h():
    """
    First copy svut_h.sv macro in the user folder if not present or different
    """

    org_hfile = SCRIPTDIR + "/svut_h.sv"
    curr_hfile = os.getcwd() + "/svut_h.sv"

    if (not os.path.isfile(curr_hfile)) or\
            (not filecmp.cmp(curr_hfile, org_hfile)):
        print("INFO: Copy up-to-date version of svut_h.sv")
        os.system("cp " + org_hfile + " " + os.getcwd())

    return 0


def find_unit_tests():
    """
    Parse all unit test files of the current folder
    and return a list of available tests
    """

    supported_prefix = ["tb_", "ts_", "testbench_", "testsuite_", "unit_test_"]
    supported_suffix = ["_unit_test.v", "_unit_test.sv",
                        "_testbench.v", "_testbench.sv",
                        "_testsuite.v", "_testsuite.sv",
                        "_tb.v", "_tb.sv", "_ts.v", "_ts.sv"]
    files = []
    # Parse the current folder
    for _file in os.listdir(os.getcwd()):
        # Check only the files
        if os.path.isfile(_file):
            for suffix in supported_suffix:
                if _file.endswith(suffix):
                    files.append(_file)
            for prefix in supported_prefix:
                if _file.startswith(prefix):
                    files.append(_file)

    # Remove duplicated file if contains both prefix and suffix
    files = list(set(files))
    return files


def print_banner(tag):
    """
    A banner printed when the flow starts
    """
    print()
    print("""       ______    ____  ________""")
    print("""      / ___/ |  / / / / /_  __/""")
    print("""      \\__ \\| | / / / / / / /  """)
    print("""     ___/ /| |/ / /_/ / / /   """)
    print("""    /____/ |___/\\____/ /_/""")
    print()
    print(f"    {tag}")
    print()

    return 0

def helper(tag):
    """
    Help menu
    """

    print_banner(tag)
    print("    https://github.com/dpretet/svut")
    print()

    return 0


def get_defines(defines):
    """
    Return a string with the list of defines ready to drop in icarus
    """
    simdefs = ""

    if not defines:
        return simdefs

    defs = defines.split(';')

    for _def in defs:
        if _def:
            simdefs += "-D" + _def + " "

    return simdefs


def create_iverilog(args, test):
    """
    Create the Icarus Verilog command to launch the simulation
    """

    cmds = []

    if not os.path.isfile("svut.out"):
        print_event("Testbench executable not found. Will build it")
        args.run_only = False

    # Build testbench executable
    if not args.run_only:

        cmd = "iverilog -g2012 -Wall -o svut.out "

        if args.define:
            cmd += get_defines(args.define)

        if args.dotfile:

            dotfiles = ""

            for dot in args.dotfile:
                if os.path.isfile(dot):
                    dotfiles += dot + " "

            if dotfiles:
                cmd += "-f " + dotfiles + " "

        if args.include:
            incs = " ".join(args.include)
            cmd += "-I " + incs + " "

        cmd += test + " "
        cmds.append(cmd)

    # Execute testbench
    if not args.compile_only:

        cmd = "vvp "
        if args.vpi:
            cmd += args.vpi + " "

        cmd += "svut.out "
        cmds.append(cmd)

    return cmds


def create_verilator(args, test):
    """
    Create the Verilator command to launch the simulation
    """

    testname = os.path.basename(test).split(".")[0]

    cmds = []

    if not os.path.isfile("build/V" + testname + ".mk"):
        print_event("Testbench executable not found. Will build it")
        args.run_only = False


    # Build testbench executable
    if not args.run_only:

        cmd = """verilator -Wall --trace --Mdir build +1800-2012ext+sv """
        cmd += """+1800-2005ext+v -Wno-STMTDLY -Wno-UNUSED -Wno-UNDRIVEN -Wno-PINCONNECTEMPTY """
        cmd += """-Wpedantic -Wno-VARHIDDEN -Wno-lint """

        if args.define:
            cmd += get_defines(args.define)

        if args.dotfile:

            dotfiles = ""

            for dot in args.dotfile:
                if os.path.isfile(dot):
                    dotfiles += dot + " "

            if dotfiles:
                cmd += "-f " + dotfiles + " "

        if args.include:
            for inc in args.include:
                cmd += "+incdir+" + inc + " "

        cmd += "-cc --exe --build -j --top-module " + testname + " "
        cmd += test + " " + args.main
        cmds.append(cmd)

    # Execution command
    if not args.compile_only:
        cmd = "build/V" + testname
        cmds.append(cmd)

    return cmds


def print_event(event):
    """
    Print an event during SVUT execution
    TODO: manage severity/verbosity level
    """

    time = datetime.datetime.now().time().strftime('%H:%M:%S')

    print("SVUT (@ " + time + ") " + event, flush=True)
    print("")

    return 0


def get_git_tag():
    """
    Return current SVUT version
    """

    curr_path = os.getcwd()
    os.chdir(SCRIPTDIR)

    try:
        git_tag = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"])
        git_tag = git_tag.strip().decode('ascii')
    except subprocess.CalledProcessError as err:
        print("WARNING: Can't get last git tag. Will return v0.0.0")
        git_tag = "v0.0.0"
        print(err.output)

    os.chdir(curr_path)
    return git_tag


if __name__ == '__main__':

    PARSER = argparse.ArgumentParser(description='SystemVerilog Unit Test Flow')

    # SVUT options

    PARSER.add_argument('-sim', dest='simulator', type=str, default="icarus",
                        help='The simulator to use, icarus or verilator.')

    PARSER.add_argument('-test', dest='test', type=str, default="all", nargs="*",
                        help='Unit test to run. A file or a list of files')

    PARSER.add_argument('-no-splash', dest='splash', default=False, action='store_true',
                        help='Don\'t print the banner when executing')

    PARSER.add_argument('-version', dest='version', action='store_true',
                        default="", help='Print version menu')

    # Simulator options

    PARSER.add_argument('-f', dest='dotfile', type=str, default=["files.f"], nargs="*",
                        help="A dot file (*.f) with incdir, define and file path")

    PARSER.add_argument('-include', dest='include', type=str, nargs="*",
                        default="", help='Specify an include folder; can be used along a dotfile')

    PARSER.add_argument('-main', dest='main', type=str, default="sim_main.cpp",
                        help='Verilator main cpp file, like sim_main.cpp')

    PARSER.add_argument('-define', dest='define', type=str, default="",
                        help='''A list of define separated by ; \
                            ex: -define "DEF1=2;DEF2;DEF3=3"''')

    PARSER.add_argument('-vpi', dest='vpi', type=str, default="",
                        help='''A string of arguments passed as is to Icarus (only), separated by a space\
                            ex: -vpi "-M. -mMyVPI"''')

    # SVUT Execution options

    PARSER.add_argument('-run-only', dest='run_only', default=False, action='store_true',
                        help='Only run existing executable but build it if not present')

    PARSER.add_argument('-compile-only', dest='compile_only', default=False, action='store_true',
                        help='Only prepare the testbench executable')

    PARSER.add_argument('-dry-run', dest='dry', default=False, action='store_true',
                        help='Just print the command, don\'t execute')


    ARGS = PARSER.parse_args()

    GIT_TAG = get_git_tag()

    if ARGS.version:
        helper(GIT_TAG)
        sys.exit(0)

    if not ARGS.splash:
        print_banner(GIT_TAG)

    # Lower the simulator name to ease checking
    ARGS.simulator = ARGS.simulator.lower()
    # Check arguments consistency
    check_arguments(ARGS)

    # If the user doesn't specify a path, scan the folder to execute all testbenchs
    if ARGS.test == "all":
        ARGS.test = find_unit_tests()

    # Copy svut_h.sv if not present or not up-to-date
    copy_svut_h()

    cmdret = 0

    for tests in ARGS.test:

        check_tb_extension(tests)

        if "iverilog" in ARGS.simulator or "icarus" in ARGS.simulator:
            CMDS = create_iverilog(ARGS, tests)

        elif "verilator" in ARGS.simulator:
            CMDS = create_verilator(ARGS, tests)

        start = timer()
        print_event("Start " + tests)

        # Execute commands one by one
        for CMD in CMDS:

            print_event(CMD)

            if not ARGS.dry:
                if os.system(CMD):
                    cmdret += 1
                    print("ERROR: Command failed: " + CMD)
                    break

        print_event("Stop " + tests)

    end = timer()
    print_event("Elapsed time: " + str(timedelta(seconds=end-start)))
    print()

    sys.exit(cmdret)
