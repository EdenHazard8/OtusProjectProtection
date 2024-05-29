# -*- coding: UTF-8 -*-
from datetime import datetime
from operator import itemgetter

import pytest
import re
import warnings
import logging

# Reference: http://docs.gurock.com/testrail-api2/reference-statuses
TESTRAIL_TEST_STATUS = {
    "passed": 1,
    "blocked": 2,
    "untested": 3,
    "retest": 4,
    "failed": 5
}

PYTEST_TO_TESTRAIL_STATUS = {
    "passed": TESTRAIL_TEST_STATUS["passed"],
    "failed": TESTRAIL_TEST_STATUS["failed"],
    "skipped": TESTRAIL_TEST_STATUS["blocked"],
}

DT_FORMAT = '%d-%m-%Y %H:%M:%S'

TESTRAIL_PREFIX = 'testrail'
TESTRAIL_DEFECTS_PREFIX = 'testrail_defects'
ADD_RESULTS_URL = 'add_results_for_cases/{}'
ADD_TESTRUN_URL = 'add_run/{}'
CLOSE_TESTRUN_URL = 'close_run/{}'
CLOSE_TESTPLAN_URL = 'close_plan/{}'
GET_TESTRUN_URL = 'get_run/{}'
GET_TESTPLAN_URL = 'get_plan/{}'
GET_TESTS_URL = 'get_tests/{}'
ADD_PLAN_ENTRY_URL = 'add_plan_entry/{}'
GET_TESTPLANS_URL = 'get_plans/{}'
ADD_TESTPLAN_URL = 'add_plan/{}'
UPDATE_TESTPLAN = 'update_plan_entry/{}/{}'
UPDATE_TESTRUN_IN_TESTPLAN = 'update_run_in_plan_entry/{}'
UPDATE_TESTRUN = 'update_run/{}'
GET_TESTRUNS_URL = 'get_runs/{}'

COMMENT_SIZE_LIMIT = 4000


class DeprecatedTestDecorator(DeprecationWarning):
    pass


warnings.simplefilter(action='once', category=DeprecatedTestDecorator, lineno=0)


class pytestrail(object):
    '''
    An alternative to using the testrail function as a decorator for test cases, since py.test may confuse it as a test
    function since it has the 'test' prefix
    '''

    @staticmethod
    def case(*ids):
        """
        Decorator to mark tests with testcase ids.

        ie. @pytestrail.case('C123', 'C12345')

        :return pytest.mark:
        """
        return pytest.mark.testrail(ids=ids)

    @staticmethod
    def defect(*defect_ids):
        """
                Decorator to mark defects with defect ids.

                ie. @pytestrail.defect('PF-513', 'BR-3255')

                :return pytest.mark:
                """
        return pytest.mark.testrail_defects(defect_ids=defect_ids)


def testrail(*ids):
    """
    Decorator to mark tests with testcase ids.

    ie. @testrail('C123', 'C12345')

    :return pytest.mark:
    """
    deprecation_msg = ('pytest_testrail: the @testrail decorator is deprecated and will be removed. Please use the '
                       '@pytestrail.case decorator instead.')
    warnings.warn(deprecation_msg, DeprecatedTestDecorator)
    return pytestrail.case(*ids)


def get_test_outcome(outcome):
    """
    Return numerical value of test outcome.

    :param str outcome: pytest reported test outcome value.
    :returns: int relating to test outcome.
    """
    return PYTEST_TO_TESTRAIL_STATUS[outcome]


def testrun_name():
    """Returns testrun name with timestamp"""
    now = datetime.utcnow()
    return 'Automated Run {}'.format(now.strftime(DT_FORMAT))


def clean_test_ids(test_ids):
    """
    Clean pytest marker containing testrail testcase ids.

    :param list test_ids: list of test_ids.
    :return list ints: contains list of test_ids as ints.
    """
    return [int(re.search('(?P<test_id>[0-9]+$)', test_id).groupdict().get('test_id')) for test_id in test_ids]


def clean_test_defects(defect_ids):
    """
        Clean pytest marker containing testrail defects ids.

        :param list defect_ids: list of defect_ids.
        :return list ints: contains list of defect_ids as ints.
        """
    return [(re.search('(?P<defect_id>.*)', defect_id).groupdict().get('defect_id')) for defect_id in defect_ids]


def get_testrail_keys(items):
    """Return Tuple of Pytest nodes and TestRail ids from pytests markers"""
    testcaseids = []
    for item in items:
        if not item.get_closest_marker('skip'):
            if item.get_closest_marker(TESTRAIL_PREFIX):
                testcaseids.append(
                    (
                        item,
                        clean_test_ids(
                            item.get_closest_marker(TESTRAIL_PREFIX).kwargs.get('ids')
                        )
                    )
                )
    return testcaseids


class PyTestRailPlugin(object):
    def __init__(self, client, assign_user_id, project_id, suite_id, include_all, cert_check,
                 tr_name, tr_description='', run_id=0, plan_id=0, version='', close_on_complete=False,
                 publish_blocked=True, skip_missing=False, milestone_id=None, custom_comment=None,
                 update=False, testplan_name=None, publish_errors=False, custom_fields=None,
                 merge_parametrize=False):
        self.update = update
        self.assign_user_id = assign_user_id
        self.cert_check = cert_check
        self.client = client
        self.project_id = project_id
        self.results = []
        self.suite_id = suite_id
        self.include_all = include_all
        self.testrun_name = tr_name
        self.testrun_description = tr_description
        self.testrun_id = run_id
        self.testplan_id = plan_id
        self.version = version
        self.close_on_complete = close_on_complete
        self.publish_blocked = publish_blocked
        self.skip_missing = skip_missing
        self.milestone_id = milestone_id
        self.custom_comment = custom_comment
        self.testplan_name = testplan_name
        self.publish_errors = publish_errors
        self.custom_fields = custom_fields
        self.merge_parametrize = merge_parametrize

        if run_id:
            logging.warning('--tr-run-id - Этот параметр будет в последующем удалён, пожалуйста не используйте его')
        if plan_id:
            logging.warning('--tr-plan-id - Этот параметр будет в последующем удалён, пожалуйста не используйте его')
        if skip_missing:
            logging.warning('--tr-skip-missing - Этот параметр будет в последующем удалён, пожалуйста не используйте его')
        if update:
            logging.warning('--tr-update - Этот параметр будет в последующем удалён, пожалуйста не используйте его')

    # pytest hooks

    def pytest_report_header(self, config, startdir):
        """ Add extra-info in header """
        message = 'pytest-testrail: '
        if self.testplan_name and self.testrun_name:
            message += 'selected testrun {} in testplan {}'.format(self.testrun_name, self.testplan_name)
        elif self.testrun_name:
            message += 'selected testrun {}'.format(self.testrun_name)
        else:
            message += 'no action'

        return message

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        if self.merge_parametrize:
            pytest.name_tests = {}

        items_with_tr_keys = get_testrail_keys(items)
        tr_keys = [case_id for item in items_with_tr_keys for case_id in item[1]]

        if not self.testrun_name:
            self.testrun_id = 0
            self.testplan_id = 0

        # вариант работы с параметризацией тест-ранов (testrun_id передаём)
        elif self.testrun_id and self.testplan_name and self.testrun_name:
            for testrail_plan in self.get_plans():
                if self.testplan_name == testrail_plan['name']:
                    self.testplan_id = testrail_plan['id']
                    break
            tests_list = [
                test.get('case_id') for test in self.get_tests(self.testrun_id)
            ]
            update_tr_keys = set(tests_list + tr_keys)
            if len(update_tr_keys) > len(set(tests_list)):
                self.update_run_in_plan_entry(self.testrun_id,
                                              tr_keys=list(update_tr_keys))

        # вариант работы без параметризации тест-ранов (testrun_id не передаём)
        elif self.testplan_name and self.testrun_name:
            for testrail_plan in self.get_plans():
                if self.testplan_name == testrail_plan['name']:
                    self.testplan_id = testrail_plan['id']
                    break
            else:
                self.add_plan(self.project_id, self.testplan_name)
            
            if self.find_testrun_in_testplan():
                self.testrun_id = self.get_testrun_id_in_testplan()
                tests_list = [
                    test.get('case_id') for test in self.get_tests(self.testrun_id)
                ]
                update_tr_keys = set(tests_list + tr_keys)
                if len(update_tr_keys) > len(set(tests_list)):
                    entry_id = self.get_entry_id()
                    self.update_plan_entry(
                        self.testplan_id,
                        entry_id,
                        self.testrun_name,
                        tr_keys=list(update_tr_keys),
                    )
                self.testrun_id = 0
            else:
                self.add_plan_entry(
                    self.testplan_id,
                    self.suite_id,
                    self.testrun_name,
                    self.assign_user_id,
                    self.include_all,
                    tr_keys,
                    self.testrun_description,
                )

        elif self.testrun_name:
            if self.find_testrun():
                self.testrun_id = self.get_testrun_id()
                tests_list = [
                    test.get('case_id') for test in self.get_tests(self.testrun_id)
                ]
                update_tr_keys = set(tests_list + tr_keys)
                if len(update_tr_keys) > len(set(tests_list)):
                    self.update_run(self.testrun_id, tr_keys=list(update_tr_keys))
            else:
                self.create_test_run(
                    self.assign_user_id,
                    self.project_id,
                    self.suite_id,
                    self.include_all,
                    self.testrun_name,
                    tr_keys,
                    self.milestone_id,
                    self.testrun_description
                )

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        """ Collect result and associated testcases (TestRail) of an execution """
        outcome = yield
        rep = outcome.get_result()
        defectids = None
        if 'callspec' in dir(item):
            test_parametrize = item.callspec.params
        else:
            test_parametrize = None
        comment = rep.longrepr
        if item.get_closest_marker(TESTRAIL_DEFECTS_PREFIX):
            defectids = item.get_closest_marker(TESTRAIL_DEFECTS_PREFIX).kwargs.get('defect_ids')
        if item.get_closest_marker(TESTRAIL_PREFIX):
            testcaseids = item.get_closest_marker(TESTRAIL_PREFIX).kwargs.get('ids')
            if rep.when == 'call' and testcaseids or rep.failed and testcaseids and self.publish_errors:
                if self.merge_parametrize:
                    test_name = rep.nodeid.split('[')[0]
                    if test_name not in pytest.name_tests:
                        pytest.name_tests[test_name] = rep.outcome
                        self.add_result(
                            clean_test_ids(testcaseids),
                            get_test_outcome(outcome.get_result().outcome),
                            comment=comment,
                            duration=rep.duration,
                            defects=str(clean_test_defects(defectids)).replace('[', '').replace(']', '').replace("'", '') if defectids else None,
                            test_parametrize=test_parametrize
                        )
                    else:
                        if rep.outcome == 'failed':
                            if pytest.name_tests[test_name] == 'passed':
                                self.add_result(
                                    clean_test_ids(testcaseids),
                                    get_test_outcome(outcome.get_result().outcome),
                                    comment=comment,
                                    duration=rep.duration,
                                    defects=str(clean_test_defects(defectids)).replace('[', '').replace(']', '').replace("'", '') if defectids else None,
                                    test_parametrize=test_parametrize
                                )
                                pytest.name_tests[test_name] = rep.outcome
                            
                else:
                    self.add_result(
                            clean_test_ids(testcaseids),
                            get_test_outcome(outcome.get_result().outcome),
                            comment=comment,
                            duration=rep.duration,
                            defects=str(clean_test_defects(defectids)).replace('[', '').replace(']', '').replace("'", '') if defectids else None,
                            test_parametrize=test_parametrize
                        )

    def pytest_sessionfinish(self, session, exitstatus):
        """ Publish results in TestRail """
        print('[{}] Start publishing'.format(TESTRAIL_PREFIX))
        if self.results:
            tests_list = [str(result['case_id']) for result in self.results]
            print('[{}] Testcases to publish: {}'.format(TESTRAIL_PREFIX, ', '.join(tests_list)))

            if self.testrun_id:
                self.add_results(self.testrun_id)
            elif self.testplan_id:
                testrun_id = self.get_testrun_id_in_testplan()
                print('[{}] Testrun to update: {}'.format(TESTRAIL_PREFIX, testrun_id))
                self.add_results(testrun_id)
            else:
                print('[{}] No data published'.format(TESTRAIL_PREFIX))

            if self.close_on_complete and self.testrun_id:
                self.close_test_run(self.testrun_id)
            elif self.close_on_complete and self.testplan_id:
                self.close_test_plan(self.testplan_id)
        print('[{}] End publishing'.format(TESTRAIL_PREFIX))

    # plugin

    def add_result(self, test_ids, status, comment='', defects=None, duration=0, test_parametrize=None):
        """
        Add a new result to results dict to be submitted at the end.

        :param list test_parametrize: Add test parametrize to test result
        :param defects: Add defects to test result
        :param list test_ids: list of test_ids.
        :param int status: status code of test (pass or fail).
        :param comment: None or a failure representation.
        :param duration: Time it took to run just the test.
        """
        for test_id in test_ids:
            data = {
                'case_id': test_id,
                'status_id': status,
                'comment': comment,
                'duration': duration,
                'defects': defects,
                'test_parametrize': test_parametrize
            }
            self.results.append(data)

    def add_results(self, testrun_id):
        """
        Add results one by one to improve errors handling.

        :param testrun_id: Id of the testrun to feed

        """
        # unicode converter for compatibility of python 2 and 3
        try:
            converter = unicode
        except NameError:
            converter = lambda s, c: str(bytes(s, "utf-8"), c)
        # Results are sorted by 'case_id' and by 'status_id' (worst result at the end)

        # Comment sort by status_id due to issue with pytest-rerun failures,
        # for details refer to issue https://github.com/allankp/pytest-testrail/issues/100
        # self.results.sort(key=itemgetter('status_id'))
        self.results.sort(key=itemgetter('case_id'))

        # Manage case of "blocked" testcases
        if self.publish_blocked is False:
            print('[{}] Option "Don\'t publish blocked testcases" activated'.format(TESTRAIL_PREFIX))
            blocked_tests_list = [
                test.get('case_id') for test in self.get_tests(testrun_id)
                if test.get('status_id') == TESTRAIL_TEST_STATUS["blocked"]
            ]
            print('[{}] Blocked testcases excluded: {}'.format(TESTRAIL_PREFIX,
                                                               ', '.join(str(elt) for elt in blocked_tests_list)))
            self.results = [result for result in self.results if result.get('case_id') not in blocked_tests_list]

        # prompt enabling include all test cases from test suite when creating test run
        if self.include_all:
            print('[{}] Option "Include all testcases from test suite for test run" activated'.format(TESTRAIL_PREFIX))

        # Publish results
        data = {'results': []}
        for result in self.results:
            entry = {'status_id': result['status_id'], 'case_id': result['case_id'], 'defects': result['defects']}
            if self.version:
                entry['version'] = self.version
            if self.custom_fields:
                for key, value in self.custom_fields.items():
                    entry['custom_{}'.format(key)] = value
            comment = result.get('comment', '')
            test_parametrize = result.get('test_parametrize', '')
            entry['comment'] = u''
            if test_parametrize:
                entry['comment'] += u"# Test parametrize: #\n"
                entry['comment'] += str(test_parametrize) + u'\n\n'
            if comment:
                if self.custom_comment:
                    entry['comment'] += self.custom_comment + '\n'
                    # Indent text to avoid string formatting by TestRail. Limit size of comment.
                    entry['comment'] += u"# Pytest result: #\n"
                    entry['comment'] += u'Log truncated\n...\n' if len(str(comment)) > COMMENT_SIZE_LIMIT else u''
                    entry['comment'] += u"    " + converter(str(comment), "utf-8")[-COMMENT_SIZE_LIMIT:].replace('\n', '\n    ') # noqa
                else:
                    # Indent text to avoid string formatting by TestRail. Limit size of comment.
                    entry['comment'] += u"# Pytest result: #\n"
                    entry['comment'] += u'Log truncated\n...\n' if len(str(comment)) > COMMENT_SIZE_LIMIT else u''
                    entry['comment'] += u"    " + converter(str(comment), "utf-8")[-COMMENT_SIZE_LIMIT:].replace('\n', '\n    ') # noqa
            elif comment == '' or comment == None:
                if self.custom_comment:
                    entry['comment'] = self.custom_comment
            duration = result.get('duration')
            if duration:
                duration = 1 if (duration < 1) else int(round(duration))  # TestRail API doesn't manage milliseconds
                entry['elapsed'] = str(duration) + 's'
            data['results'].append(entry)

        response = self.client.send_post(
            ADD_RESULTS_URL.format(testrun_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Info: Testcases not published for following reason: "{}"'.format(TESTRAIL_PREFIX, error))

    def create_test_run(self, assign_user_id, project_id, suite_id, include_all,
                        testrun_name, tr_keys, milestone_id, description=''):
        """
        Create testrun with ids collected from markers.

        :param tr_keys: collected testrail ids.
        """
        data = {
            'suite_id': suite_id,
            'name': testrun_name,
            'description': description,
            'assignedto_id': assign_user_id,
            'include_all': include_all,
            'case_ids': tr_keys,
            'milestone_id': milestone_id
        }

        response = self.client.send_post(
            ADD_TESTRUN_URL.format(project_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to create testrun: "{}"'.format(TESTRAIL_PREFIX, error))
        else:
            self.testrun_id = response['id']
            print('[{}] New testrun created with name "{}" and ID={}'.format(TESTRAIL_PREFIX,
                                                                             testrun_name,
                                                                             self.testrun_id))

    def close_test_run(self, testrun_id):
        """
        Closes testrun.

        """
        response = self.client.send_post(
            CLOSE_TESTRUN_URL.format(testrun_id),
            data={},
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to close test run: "{}"'.format(TESTRAIL_PREFIX, error))
        else:
            print('[{}] Test run with ID={} was closed'.format(TESTRAIL_PREFIX, self.testrun_id))

    def close_test_plan(self, testplan_id):
        """
        Closes testrun.

        """
        response = self.client.send_post(
            CLOSE_TESTPLAN_URL.format(testplan_id),
            data={},
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to close test plan: "{}"'.format(TESTRAIL_PREFIX, error))
        else:
            print('[{}] Test plan with ID={} was closed'.format(TESTRAIL_PREFIX, self.testplan_id))

    # def is_testrun_available(self):
    #     """
    #     Ask if testrun is available in TestRail.

    #     :return: True if testrun exists AND is open
    #     """
    #     response = self.client.send_get(
    #         GET_TESTRUN_URL.format(self.testrun_id),
    #         cert_check=self.cert_check
    #     )
    #     error = self.client.get_error(response)
    #     if error:
    #         print('[{}] Failed to retrieve testrun: "{}"'.format(TESTRAIL_PREFIX, error))
    #         return False

    #     return response['is_completed'] is False

    # def is_testplan_available(self):
    #     """
    #     Ask if testplan is available in TestRail.

    #     :return: True if testplan exists AND is open
    #     """
    #     response = self.client.send_get(
    #         GET_TESTPLAN_URL.format(self.testplan_id),
    #         cert_check=self.cert_check
    #     )
    #     error = self.client.get_error(response)
    #     if error:
    #         print('[{}] Failed to retrieve testplan: "{}"'.format(TESTRAIL_PREFIX, error))
    #         return False

    #     return response['is_completed'] is False

    # def get_available_testruns(self, plan_id):
    #     """
    #     :return: a list of available testruns associated to a testplan in TestRail.

    #     """
    #     testruns_list = []
    #     response = self.client.send_get(
    #         GET_TESTPLAN_URL.format(plan_id),
    #         cert_check=self.cert_check
    #     )
    #     error = self.client.get_error(response)
    #     if error:
    #         print('[{}] Failed to retrieve testrun: "{}"'.format(TESTRAIL_PREFIX, error))
    #     else:
    #         for entry in response['entries']:
    #             for run in entry['runs']:
    #                 if not run['is_completed']:
    #                     testruns_list.append(run['id'])
    #     return testruns_list

    def get_tests(self, run_id):
        """
        :return: the list of tests containing in a testrun.

        """
        response = self.client.send_get(
            GET_TESTS_URL.format(run_id),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to get tests: "{}"'.format(TESTRAIL_PREFIX, error))
            return None
        return response['tests']

    def add_plan_entry(self, testplan_id, suite_id, testrun_name, assign_user_id,
                       include_all=False, tr_keys=None, description=None, config_ids=None,
                       refs=None, runs=None):
        data = {
            'suite_id': suite_id,
            'name': testrun_name,
            'description': description,
            'assignedto_id': assign_user_id,
            'include_all': include_all,
            'case_ids': tr_keys,
            'config_ids': config_ids,
            'refs': refs,
            'runs': runs,

        }
        response = self.client.send_post(
            ADD_PLAN_ENTRY_URL.format(testplan_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)

        if error:
            print('[{}] Failed to add plan entry: "{}"'.format(TESTRAIL_PREFIX, error))
        else:
            self.testrun_id = response['runs'][0]['id']
            print('[{}] Add plan entry created with name "{}" and ID={}'.format(TESTRAIL_PREFIX,
                                                                                testrun_name,
                                                                                self.testrun_id))

    def get_plans(self, filters='&is_completed=0'):
        """
        :return: the list of plans containing in a project.

        """
        response = self.client.send_get(
            GET_TESTPLANS_URL.format("{}{}".format(self.project_id, filters)),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to retrieve testplans: "{}"'.format(TESTRAIL_PREFIX, error))
            return None
        return response['plans']

    def add_plan(self, project_id, name, description=None, milestone_id=None, entries=None):
        """
        :return: plan in a project.

        """
        data = {
            'name': name,
            'description': description,
            'milestone_id': milestone_id,
            'entries': entries,

        }
        response = self.client.send_post(
            ADD_TESTPLAN_URL.format(project_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)

        if error:
            print('[{}] Failed to add plan: "{}"'.format(TESTRAIL_PREFIX, error))
        else:
            self.testplan_id = response['id']
            print('[{}] Add plan created with name "{}" and ID={}'.format(TESTRAIL_PREFIX,
                                                                          name,
                                                                          self.testplan_id))

    def update_plan_entry(self, testplan_id, entry_id, testrun_name, description=None,
                          assign_user_id=None, include_all=False, tr_keys=None, refs=None):
        data = {
            'name': testrun_name,
            'description': description,
            'assignedto_id': assign_user_id,
            'include_all': include_all,
            'case_ids': tr_keys,
            'refs': refs,
        }
        response = self.client.send_post(
            UPDATE_TESTPLAN.format(testplan_id, entry_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to update testplan: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при обновлении testplan")

    def update_run_in_plan_entry(self, testrun_id, description=None, tr_keys=None,
                                 assign_user_id=None, include_all=False, refs=None):
        data = {
            'description': description,
            'assignedto_id': assign_user_id,
            'include_all': include_all,
            'case_ids': tr_keys,
            'refs': refs,
        }
        response = self.client.send_post(
            UPDATE_TESTRUN_IN_TESTPLAN.format(testrun_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to update testrun: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при обновлении testplan")

    def update_run(self, testrun_id, description=None, include_all=False, tr_keys=None):
        data = {
            'description': description,
            'include_all': include_all,
            'case_ids': tr_keys,
        }
        response = self.client.send_post(
            UPDATE_TESTRUN.format(testrun_id),
            data,
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to update testrun: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при обновлении testrun")

    def get_entry_id(self):
        """
        :return: entry id testrun associated to a test plan in TestRail.

        """
        response = self.client.send_get(
            GET_TESTPLAN_URL.format(self.testplan_id),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to retrieve testplan: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при поиске testplan")

        for entry in response['entries']:
            if entry['name'] == self.testrun_name:
                entry_id = entry['id']
                break
        else:
            raise Exception("Ошибка, в testplan не обнаружен искомый testrun")
        return entry_id

    def get_testrun_id_in_testplan(self):
        """
        :return: testrun id associated to a test plan in TestRail.

        """
        response = self.client.send_get(
            GET_TESTPLAN_URL.format(self.testplan_id),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to retrieve testplan: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при поиске testplan")

        for entry in response['entries']:
            if entry['name'] == self.testrun_name:
                testrun_id = entry['runs'][0]['id']
                break
        else:
            raise Exception("Ошибка, в testplan не обнаружен искомый testrun")
        return testrun_id

    def find_testrun_in_testplan(self):
        """
        :return: True if testrun exists AND is open

        """
        response = self.client.send_get(
            GET_TESTPLAN_URL.format(self.testplan_id),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to retrieve testrun: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при поиске testplan")

        if len(response['entries']) == 0:
            return False
        for entry in response['entries']:
            if entry['name'] == self.testrun_name:
                break
        else:
            return False
        return True

    def get_testrun_id(self, filters='&is_completed=0'):
        """
        :return: testrun id not associated to a test plan in TestRail.

        """
        response = self.client.send_get(
            GET_TESTRUNS_URL.format("{}{}".format(self.project_id, filters)),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to retrieve testrun: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при поиске testrun")

        for testrun in response['runs']:
            if testrun['name'] == self.testrun_name:
                testrun_id = testrun['id']
                break
        else:
            raise Exception("Ошибка, в проекте не обнаружен искомый testrun")
        return testrun_id

    def find_testrun(self):
        """
        :return: True if testrun exists AND is open

        """
        response = self.client.send_get(
            GET_TESTRUNS_URL.format(self.project_id),
            cert_check=self.cert_check
        )
        error = self.client.get_error(response)
        if error:
            print('[{}] Failed to retrieve testrun: "{}"'.format(TESTRAIL_PREFIX, error))
            raise Exception("Ошибка при поиске testrun")

        if len(response['runs']) == 0:
            return False
        for testrun in response['runs']:
            if testrun['name'] == self.testrun_name:
                break
        else:
            return False
        return True
