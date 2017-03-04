#!/usr/bin/env python3

import argparse
from colorama import Fore, Style
from functools import wraps
import re
import sys


class UnicodeCharacters:
    success = '✓'
    fail = '✗'


class AsciiCharacters:
    success = 'OK'
    fail = ' X'


class LineHandler(object):
    def __init__(self):
        self._handlers = []

    def process(self, owner, line):
        for h in self._handlers:
            if h(owner, line):
                return True

    def add(self, regex):
        if isinstance(regex, str):
            regex = re.compile(regex)

        def decorator(f):
            @wraps(f)
            def wrapper(self, line):
                m = regex.search(line)
                if not m:
                    return False
                result = f(self, *m.groups())
                if result is not None:
                    return result
                else:
                    return True

            self._handlers.append(wrapper)

            return wrapper

        return decorator


class Parser(object):
    TIME_RE = r'(?: \((\d+) ms(?: total)?\))?'

    handler = LineHandler()

    def __init__(self, output):
        self.output = output

        self.total_test_count = 0
        self.total_test_case_count = 0
        self.test_case_index = 0

        self.current_test_case = None
        self.current_test_count = 0
        self.current_test = None
        self.test_index = 0
        self.current_fail_count = 0

    def process(self, line):
        if not self.handler.process(self, line):
            self.output.raw_output(self.current_test, line)

    @handler.add(r'Running (\d+) tests? from (\d+) test cases?')
    def start(self, total_test_count, total_test_case_count):
        self.total_test_count = int(total_test_count)
        self.total_test_case_count = int(total_test_case_count)

    @handler.add(r'\[-+\] (\d+) tests? from (.*?)(?:, where (.*?))?' + TIME_RE + '$')
    def start_stop_test_case(self, test_count, test_case, where=None, time=None):
        if time is not None:
            time = int(time)

        self.current_test = None
        if not self.current_test_case:
            self.current_test_case = test_case
            self.current_test_count = int(test_count)
            self.current_fail_count = 0
            self.test_index = 0
            self.test_case_index += 1

            self.output.start_test_case(
                test_case, self.test_case_index, self.total_test_case_count, where)
        else:
            self.output.stop_test_case(
                test_case, self.test_case_index, self.total_test_case_count,
                self.current_test_count, self.current_fail_count, time)
            self.current_test_case = None

    @handler.add(r'\[ *RUN *\] (.*)\.(.*)')
    def start_test(self, test_case, test):
        self.current_test = None
        self.test_index += 1
        self.output.start_test(test_case, test, self.test_index, self.current_test_count)

    @handler.add(r'\[ *(OK|FAILED) *\] (.*)\.(.*?)' + TIME_RE + '$')
    def stop_test(self, status, test_case, test, time=None):
        self.current_test = None
        if status == 'FAILED':
            self.current_fail_count += 1
        self.output.stop_test(
            status, test_case, test, self.test_index, self.current_test_count, time)

    @handler.add(r'^$')
    def blank_line(self):
        if self.current_test_case:
            return False


class ListOutput(object):
    def __init__(self, characters=UnicodeCharacters, print_time=0):
        self.characters = characters
        self.print_time = print_time

        # Internal state
        self.needs_newline = False

    def progress(self, current, total):
        total = str(total)
        return '%*i / ' % (len(total), current) + total

    def space_for_progress(self, current, total):
        return ' ' * len(self.progress(current, total))

    def print_line(self, test_case, test_case_index, total_test_case_count, character,
                   color=None, details=None):
        if self.needs_newline:
            print('\r' + self.progress(test_case_index, total_test_case_count), end='')
        else:
            print(self.space_for_progress(test_case_index, total_test_case_count), end='')

        if color:
            print(color, end='')
        print(' ' + character + ' ' + test_case, end='')
        if details:
            print(details)
        if color:
            print(Style.RESET_ALL, end='')

    def raw_output(self, test, line):
        if self.needs_newline:
            print()
            self.needs_newline = False

        # Line is already newline-terminated, so use end=''
        print(line, end='')

    def start_test_case(self, test_case, test_case_index, total_test_case_count, where=None):
        self.print_line(test_case, test_case_index, total_test_case_count, ' ')
        self.needs_newline = True

    def stop_test_case(self, test_case, test_case_index, total_test_case_count,
                       test_count, fail_count, time=None):
        if not fail_count:
            self.print_line(test_case, test_case_index, total_test_case_count,
                            self.characters.success, Fore.GREEN)
        else:
            self.print_line(test_case, test_case_index, total_test_case_count,
                            self.characters.fail, Fore.RED,
                            ' - %i/%i failures' % (fail_count, test_count))

        if time is not None and time >= self.print_time:
            print(' (%s ms)' % time)
        else:
            print()

        self.needs_newline = False

    def start_test(self, test_case, test, test_index, test_count):
        pass

    def stop_test(self, status, test_case, test, test_index, test_count, time=None):
        pass


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--ascii', action='store_true',
                           help='Use ASCII progress / status, not Unicode')
    argparser.add_argument('--print_time', type=int, default=100,
                           help='Only print times greater than N milliseconds')
    args = argparser.parse_args()

    output_kwargs = {}
    if args.ascii:
        output_kwargs['characters'] = AsciiCharacters
    output_kwargs['print_time'] = args.print_time

    parser = Parser(ListOutput(**output_kwargs))

    for line in sys.stdin:
        parser.process(line)


if __name__ == '__main__':
    main()
