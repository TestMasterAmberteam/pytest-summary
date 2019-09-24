#! /usr/bin/python3
"""Module that produces summary report in HTML format. The report contains only PASS/FAIL results"""
import json
import sqlite3
from datetime import datetime
from time import time

import pytest
from _pytest.reports import TestReport
from jinja2 import Template
from pygit2 import Repository
from selenium.webdriver.remote.webdriver import WebDriver

RESULTS_DB_NAME = 'summary.sqlite3'
REPORT_TEMPLATE = '''
<html>
<head>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.css" rel="stylesheet">
    <link rel="stylesheet" href="https://use.fontawesome.com/releases/v5.8.1/css/all.css" integrity="sha384-50oBUHEmvpQ+1lW4y57PTFmhCaXp0ML5d60M1M7uH2+nqUivzIebhndOJK28anvf" crossorigin="anonymous">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.8.0/Chart.min.js" integrity="sha256-Uv9BNBucvCPipKQ2NS9wYpJmi8DTOEfTA/nH2aoJALw=" crossorigin="anonymous"></script>
</head>
<body>
    <h1>Report of tests with "{{ branch }}" git branch</h1>
    <h2>Summary</h2>
    <div class="row">
        <div class="six columns">
            <table class="">
                <thead>
                    <tr><th>Status</th><th>#</th><th>Description</th></tr>
                </thead>
                <tbody>
                    <tr bgcolor="#f65757"><td>Failed</td><td>{{ stats["failed"] }}</td><td>Test that were run and failed.</td></tr>
                    <tr bgcolor="#f3f657"><td>XFailed</td><td>{{ stats["xfail"] }}</td><td>Expected fail. Test that were run and were expected to fail and failed.</td></tr>
                    <tr bgcolor="#f0f0f0"><td>Skipped</td><td>{{ stats["skipped"] }}</td><td>Test that were not run.</td></tr>
                    <tr bgcolor="#ddffbd"><td>XPassed</td><td>{{ stats["xpass"] }}</td><td>Unexpected pass. Test that were run and were expected to fail but passed.</td></tr>
                    <tr bgcolor="#a4f657"><td>Passed</td><td>{{ stats["passed"] }}</td><td>Test that were run and finished OK.</td></tr>
                    <tr><td><b>Total</b></td><td><b>{{ total }}</b></td><td></td></tr>
                </tbody>
            </table>
        </div>
        <div class="six columns"><canvas id="summary"></canvas></div>
        <script>
        var ctx = document.getElementById('summary').getContext('2d');
        var summaryChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ["Passed", 'Failed', 'Skipped', 'XFailed', 'XPassed', ],
                datasets: [{
                    label: "Test results",
                    data: [{{ stats["failed"] }}, {{ stats["xfail"] }}, {{ stats["skipped"] }},  {{ stats["xpass"] }}, {{ stats["passed"] }}],
                    backgroundColor: ["#f65757", "#f3f657", "#f0f0f0",  "#ddffbd", "#a4f657"],
                    borderWidth: 1
                }]
            }
        })
        </script>
    </div>  
    <h2>Latest results</h2>
    <table class="u-full-width">
        <thead>
            <tr><th>Test</th><th>Capabilities</th><th>Phase</th><th>Outcome</th></tr>
        </thead>
        <tbody>
        {% for bgcolor, test, capabilities, phase, outcome, xfail_reason, video_url in results %}
            <tr bgcolor="{{ bgcolor }}"><td><a href="#history_{{test}}">{{ test.replace('::', '<br/>') }}</a></td><td>{{ capabilities }}</td><td>{{ phase }}</td>
                <td>{{ outcome }}{{ xfail_reason }}</td><td style="padding: 15px;">{{ video_url }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    <h2>Trends</h2>
        {% for test in trends %}
        <div class="row">
            <div class="four columns" style="word-wrap: break-word">{{ test['name'].replace('::', '<br/>') }}</div>
            <div class="eight columns"><canvas id="history_{{ test['name'] }}" height=50></canvas></div>
            <script>
            var ctx = document.getElementById('history_{{ test['name'] }}').getContext('2d');
            var summaryChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: [{% for data in test['data'] %}"{{ data['label']}}", {% endfor %}],
                    datasets: [{
                        data: [{% for data in test['data'] %}"{{ data['value']}}", {% endfor %}],
                        backgroundColor: [{% for data in test['data'] %}"{{ data['color']}}", {% endfor %}],
                        borderWidth: 1,
                        yAxisID: 'display'
                    }]
                },
                options: {
                    scales: {
                        xAxes: [{ barPercentage:1.0, categoryPercentage:1.0, gridLines:{ display:false }}],
                        yAxes: [{ id: 'display', ticks: { min:0, max:5, stepSize:1 }, gridLines:{ display:false }, display: false},
                                { id: 'label', type: 'category', labels: ['Failed', 'XFailed', 'Skipped', 'XPassed', 'Passed', '---']}]
                    },
                    legend: { display:false}
                }
            })
            </script>
        </div>
        {% endfor %}
	</body>
</html>
'''
VALUE_MAP = {'passed': 1, 'xpass': 2, 'skipped': 3, 'xfail': 4, 'failed': 5}
COLOR_MAP = {'passed': '#a4f657', 'xpass': '#ddffbd', 'skipped': '#f0f0f0', 'xfail': '#f3f657', 'failed': '#f65757'}
CUT_OFF_TIME = 7 * 60 * 60 * 24
build = None


def pytest_sessionstart(session):
    global build
    # set current biuild
    build = int(time())
    # initialize database if necessary
    conn = sqlite3.connect(f'{session.config.rootdir}/{RESULTS_DB_NAME}')
    c = conn.cursor()
    c.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name='result' ''')  # check if table exists
    table = c.fetchone()
    if not table:
        c.execute(
            '''CREATE TABLE result (build integer, test text, capabilities text, phase text, outcome text, xfail_reason text, video_url text)''')
    else:
        c.execute('''DELETE FROM result WHERE build < ?''', (build - CUT_OFF_TIME,)) # remove builds older than CUT_OFF
    conn.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    global build
    outcome = yield
    rep: TestReport = outcome.get_result()

    conn = sqlite3.connect(f'{item.config.rootdir}/{RESULTS_DB_NAME}')
    c = conn.cursor()
    c.execute('SELECT * FROM result WHERE test = ? and build = ?', (rep.nodeid, build))
    row = c.fetchone()
    if not row:
        if 'capabilities' in item.funcargs and item.funcargs['capabilities']:
            capabilities = json.dumps(item.funcargs['capabilities'])
        else:
            capabilities = ''
        reason = None
        if call.when == 'setup' and rep.outcome == 'skipped':
            if rep.longrepr:
                reason = rep.longrepr[-1]
        c.execute('INSERT INTO result VALUES (?, ?, ?, ?, ?, ?, null)',
                  (build, item.nodeid, capabilities, rep.when, rep.outcome, reason))
        # (item.nodeid, capabilities, rep.when, rep.outcome))
    else:  # update result if has been 'passed' and in this phase is 'failed'
        (c_build, test, capabilities, phase, old_outcome, xfail_reason, video_url) = row
        if old_outcome == 'passed':
            outcome = rep.outcome
            if rep.when == 'call' and rep.outcome == 'skipped' and 'xfail' in rep.keywords:
                outcome = 'xfail'
                # check test markers
                if hasattr(item, 'own_markers'):
                    for marker in item.own_markers:
                        if marker.name == 'xfail':
                            xfail_reason = marker.kwargs['reason']
                # check class markers
                if hasattr(item.cls, 'pytesymark'):
                    for marker in item.cls.pytestmark:
                        if marker.name == 'xfail':
                            xfail_reason = marker.kwargs['reason']
            if rep.when == 'teardown' and rep.outcome == 'passed' and 'xfail' in rep.keywords:
                outcome = 'xpass'
            c.execute('UPDATE result SET phase = ?, outcome = ?, xfail_reason = ? WHERE test = ? and build = ?',
                      (rep.when, outcome, xfail_reason, rep.nodeid, c_build))
        if rep.when == 'call' and hasattr(item.instance, 'driver') \
                and type(item.instance.driver) is WebDriver:  # add url for video if remote WebDriver
            video_url = item.instance.get_video_url()
            c.execute('UPDATE result SET video_url = ? WHERE test = ? and build = ?', (video_url, rep.nodeid, c_build))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # title
    repo = Repository('.git')  # TODO: add reaction to running tests not from git repo
    branch = repo.head.name.split('/')[-1]

    # summary
    connection = sqlite3.connect(RESULTS_DB_NAME)
    cursor = connection.cursor()

    stats = {'passed': 0, 'failed': 0, 'skipped': 0, 'xfail': 0, 'xpass': 0}
    total = 0
    results = []
    trends = []
    # get all tests
    cursor.execute('SELECT DISTINCT test FROM result ORDER BY test')
    tests = cursor.fetchall()
    for (test,) in tests:
        cursor.execute('SELECT * FROM (SELECT * FROM result WHERE test = ? ORDER BY build DESC LIMIT 10) ORDER BY build ASC', (test,))
        rows = cursor.fetchall()
        # region report and stats
        # build results
        (build, test_name, capabilities, phase, outcome, xfail_reason, video_url) = rows[-1]
        # stats
        stats[outcome] += 1
        total += 1
        # report
        bgcolor = COLOR_MAP[outcome]
        # video url
        if video_url:
            video_url = f'<a href=\"{video_url}\" target="_blank"><i class="fas fa-film"/></a>'
        else:
            video_url = '<i class="fas fa-minus"/>'
        if capabilities:
            capabilities = json.loads(capabilities)
            if 'name' in capabilities.keys():
                del capabilities['name']
            if 'build' in capabilities.keys():
                del capabilities['build']
            if 'testFileNameTemplate' in capabilities.keys():
                del capabilities['testFileNameTemplate']
        xfail_reason = f'<br/>{xfail_reason}' if xfail_reason else ''  # format xfail_reason with new line or skip
        results.append((bgcolor, test, capabilities, phase, outcome, xfail_reason, video_url))
        # endregion
        # region template
        trend = {'name': test_name, 'data': []}
        for build, test_name, capabilities, phase, outcome, xfail_reason, video_url in rows:
            label = datetime.fromtimestamp(build).strftime('%Y-%m-%d %H:%M')
            data = {'label': label, 'value': VALUE_MAP[outcome], 'color': COLOR_MAP[outcome]}
            trend['data'].append(data)
        trends.append(trend)
    # endregion
    # region write to file
    template = Template(REPORT_TEMPLATE)
    rendered_template = template.render(branch=branch, stats=stats, total=total, results=results, trends=trends)
    summary_file = open('summary.html', 'wt')
    summary_file.write(rendered_template)
    summary_file.close()
    # endregion
