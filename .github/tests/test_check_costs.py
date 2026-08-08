import os
import tempfile
from scripts.check_costs import scan_text_for_keywords, scan_package_json_content, scan_requirements_content

PACKAGE_JSON_WITH_MAPBOX = '{"dependencies": {"mapbox-gl": "^2.0.0"}}'
PACKAGE_JSON_WITH_SAFE = '{"dependencies": {"lodash": "^4.17.21"}}'

REQ_WITH_AWS = "aws-sdk\nrequests==2.28.1\n"
REQ_SAFE = "requests==2.28.1\nflask==2.2.0\n"


def test_scan_text_for_keywords():
    assert scan_text_for_keywords('This file imports mapbox and uses tiles')
    assert not scan_text_for_keywords('No paid providers here')


def test_scan_package_json_content_positive():
    assert scan_package_json_content(PACKAGE_JSON_WITH_MAPBOX)


def test_scan_package_json_content_negative():
    assert not scan_package_json_content(PACKAGE_JSON_WITH_SAFE)


def test_scan_requirements_content_positive():
    assert scan_requirements_content(REQ_WITH_AWS)


def test_scan_requirements_content_negative():
    assert not scan_requirements_content(REQ_SAFE)
