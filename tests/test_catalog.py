"""起始目录网址规范化测试。"""

from catalog import normalize_catalog_url


def test_page_param_dropped_same_catalog():
    base = "http://sample-site:8000/a/list.html"
    assert normalize_catalog_url("http://sample-site:8000/a/list.html") == base
    assert normalize_catalog_url("http://sample-site:8000/a/list.html?page=1") == base
    assert normalize_catalog_url("http://sample-site:8000/a/list.html?page=2") == base


def test_different_catalog_paths_are_distinct():
    assert normalize_catalog_url("http://sample-site:8000/a/list.html?page=1") != normalize_catalog_url(
        "http://sample-site:8000/b/list.html?page=1"
    )


def test_fragment_and_case_and_default_port_normalized():
    assert (
        normalize_catalog_url("HTTP://SAMPLE-SITE:80/a/list.html#top")
        == "http://sample-site/a/list.html"
    )


def test_non_default_port_kept():
    assert (
        normalize_catalog_url("http://sample-site:8080/a/list.html?page=3")
        == "http://sample-site:8080/a/list.html"
    )


def test_other_query_params_kept_and_sorted():
    assert (
        normalize_catalog_url("http://h/a/list.html?b=2&page=5&a=1")
        == "http://h/a/list.html?a=1&b=2"
    )


def test_blank_and_invalid_input_does_not_crash():
    assert normalize_catalog_url("") == ""
    assert normalize_catalog_url("not a url") == "not a url"
