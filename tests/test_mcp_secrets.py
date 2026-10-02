import pytest

from quests import mcp_server


@pytest.mark.parametrize(
    "owner,path",
    [
        ("quest=12", "/api/quests/12/secrets"),
        ("step = 7", "/api/steps/7/secrets"),
        ("template=5", "/api/templates/5/secrets"),
        ("questline=3", "/api/questlines/3/secrets"),
    ],
)
def test_secret_owner_path(owner, path):
    assert mcp_server._secret_owner_path(owner) == path


@pytest.mark.parametrize("bad", ["quest", "bogus=1", "quest=x", "", "=5"])
def test_secret_owner_path_rejects_bad_owner(bad):
    with pytest.raises(ValueError, match="owner must look like"):
        mcp_server._secret_owner_path(bad)
