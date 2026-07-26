import pytest

from fetch_topo_quads import bare_key


@pytest.mark.parametrize("filename_no_ext, expected", [
    ("AL_Abbeville_East_20240208_TM_geo", "AL_Abbeville_East"),
    ("NC_Glade_Valley_20220908_TM_geo", "NC_Glade_Valley"),
    ("CT_Ansonia", "CT_Ansonia"),  # no date suffix - the inconsistency that caused the original bug
    ("WV_Princeton_20230615_TM_geo", "WV_Princeton"),
])
def test_bare_key(filename_no_ext, expected):
    assert bare_key(filename_no_ext) == expected


def test_bare_key_lets_dated_and_undated_forms_match():
    """The actual bug: some CSV rows have the dated filename, others the
    plain form, for the same physical quad - bare_key() must normalize both
    to the same key so they match against the real S3 filename listing."""
    assert bare_key("VA_Marion_20220916_TM_geo") == bare_key("VA_Marion")
