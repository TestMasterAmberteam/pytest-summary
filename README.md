# pytest-summary
This tool prepares self-contained html file with the summary of pytest tests that have been run. This file can be emailed e.g. by Jenkins to anyone interested of results of the build. 

# Usage
pytest-summary is used in two places, as a pytest plugin reporting results to the databas and as a standalone script 
that produces summary.html file.

## Pytest plugin
To allow pytest-summary to collect test results put the *summary.py* file in root folder of your project 
and put the following line in your *conftest.py*:
```python
pytest_plugins = ('summary', )
```

## Report generation
Run `summary.py` and open *summary.html*

### Sections of the report
The report has threee secition:
  - Summary
  - Latest results
  - Trends
  
### Summary
This section shows a table with statuses of the tests and number of the tests with each status. 
It also contains a pie chart with statuses. 
 
### Latest results
This sections contains a table with five columns:
  - Test - pytest test ID (file::class::method[fixtures]) divided into three lines
  - Capabilities - Selenium capabilities the test was run with
  - Phase - pytest phase of the outcome
  - Outcome - pytest outcome with the reason for skipping a test if available
  - link to Zalenium movie
  
### Trends
This section contains bar charts with the history of test results. The hight of the bar (except for its color) 
represents the risk of the outcome to the project quality.  
The oldest test run is depicted on the left side of the chart and the newest - at the right side.   

# Environment  
This tool has been developed for specific environment, some of its architecture may be hardcoded in it. E.g., 
  - Python 3.7 - it has been developed for Python 3.7, and will certainly not work with Python versions before 3.5 
  becaue usage of f-strings 
  - Jenkins - the tools uses $BUILD_NUMBER environment variable
  - Zalenium - it tries to find Zalenium test movies and present links in the table
  - sqlite3 - it creates sqlite3 database in order to preserve the history
  - git - it checkes the branch of local git repository and puts it in the document title
  - [pytest-parallel](https://pypi.org/project/pytest-parallel/) - it has been used with this library and works well with it, 
  but does not need it  
 
# Contributions
Feel free to make this tool more general, add tests, configuration and everything 
testers and test managers might need.

# Acknowledgements
Idea of this little tool has been proposed by Ziemowit Buchalski during web automation tests for [Rankomat](https://rankomat.pl/)