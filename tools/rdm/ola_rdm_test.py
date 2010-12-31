#!/usr/bin/python
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Library General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# ola_rdm_get.py
# Copyright (C) 2010 Simon Newton

'''Automated testing for RDM responders.'''

__author__ = 'nomis52@gmail.com (Simon Newton)'

import TestDefinitions
import inspect
import logging
import sys
import textwrap
from ResponderTest import ResponderTest, TestRunner, TestState
from ola import PidStore
from ola.ClientWrapper import ClientWrapper
from ola.UID import UID
from optparse import OptionParser, OptionGroup, OptionValueError


def ParseOptions():
  usage = 'Usage: %prog [options] <uid>'
  description = textwrap.dedent("""\
    Run a series of tests on a RDM responder to check the behaviour.
    This requires the OLA server to be running, and the RDM device to have been
    detected. You can confirm this by running ola_rdm_discover.py -u
    UNIVERSE""")
  parser = OptionParser(usage, description=description)
  parser.add_option('-p', '--pid_file', metavar='FILE',
                    help='The file to load the PID definitions from.')
  parser.add_option('-t', '--tests', metavar='TEST1,TEST2',
                    help='A comma separated list of tests to run.')
  parser.add_option('-d', '--debug', action='store_true',
                    help='Print debug information to assist in diagnosing '
                         'failures.')
  parser.add_option('-u', '--universe', default=0,
                    type='int',
                    help='The universe number to use, default is universe 0.')

  options, args = parser.parse_args()

  if not args:
    parser.print_help()
    sys.exit(2)

  uid = UID.FromString(args[0])
  if uid is None:
    parser.print_usage()
    print 'Invalid UID: %s' % args[0]
    sys.exit(2)

  options.uid = uid
  return options


def SetupLogging(options):
  """Setup the logging for test results."""
  level = logging.INFO

  if options.debug:
    level = logging.DEBUG

  logging.basicConfig(
      level=level,
      format='%(message)s')


def DisplaySummary(test_runner):
  """Print a summary of the tests."""
  by_category = {}
  warnings = []
  count_by_state = {}
  for test in test_runner.all_tests:
    state = test.state
    count_by_state[state] = count_by_state.get(state, 0) + 1
    warnings.extend(test.warnings)

    by_category.setdefault(test.category, {})
    by_category[test.category][state] = (1 +
        by_category[test.category].get(state, 0))

  total = sum(count_by_state.values())

  logging.info('------------- Warnings --------------')
  for warning in warnings:
    logging.info(warning)

  logging.info('------------ By Category ------------')

  for category, counts in by_category.iteritems():
    passed = counts.get(TestState.PASSED, 0)
    total_run = (passed + counts.get(TestState.FAILED, 0))
    if total_run == 0:
      continue
    percent = 1.0 * passed / total_run
    logging.info(' %20s: %2d / %2d   %.0f%%' %
                 (category, passed, total_run, percent * 100))

  logging.info('-------------------------------------')
  logging.info('%d / %d tests run, %d passed, %d failed, %d broken' % (
      total - count_by_state.get(TestState.NOT_RUN, 0),
      total,
      count_by_state.get(TestState.PASSED, 0),
      count_by_state.get(TestState.FAILED, 0),
      count_by_state.get(TestState.BROKEN, 0)))


def main():
  options = ParseOptions()
  SetupLogging(options)
  pid_store = PidStore.GetStore(options.pid_file)
  wrapper = ClientWrapper()

  global found_uid
  found_uid = False

  def UIDList(state, uids):
    global found_uid
    if not state.Succeeded():
      logging.error('Fetch failed: %s' % state.message)
    else:
      for uid in uids:
        if uid == options.uid:
          logging.debug('Found UID %s' % options.uid)
          found_uid = True
    wrapper.Stop()

  logging.debug('Fetching UID list from server')
  wrapper.Client().FetchUIDList(options.universe, UIDList)
  wrapper.Run()
  wrapper.Reset()

  if not found_uid:
    logging.error('UID %s not found in universe %d' %
      (options.uid, options.universe))
    sys.exit()

  tests = None
  if options.tests is not None:
    logging.info('Restricting tests to %s' % options.tests)
    tests = options.tests.split(',')

  logging.info('Starting tests, universe %d, UID %s' %
      (options.universe, options.uid))

  runner = TestRunner(options.universe, options.uid, pid_store, wrapper,
                      logging, tests)

  for symbol in dir(TestDefinitions):
    obj = getattr(TestDefinitions, symbol)
    if not inspect.isclass(obj):
      continue
    if obj == ResponderTest:
      continue
    if issubclass(obj, ResponderTest):
      if not runner.AddTest(obj):
        logging.info('Failed to add %s' % obj)
        sys.exit()

  runner.RunTests()
  DisplaySummary(runner)


if __name__ == '__main__':
  main()