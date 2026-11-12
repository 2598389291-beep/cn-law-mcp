from cn_law_mcp import __version__
from cn_law_mcp.cli import main


def test_version_flag(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert capsys.readouterr().out.strip() == f"cn-law-mcp {__version__}"


def test_selftest_loads_all_articles(capsys):
    assert main(["--selftest"]) == 0
    assert capsys.readouterr().out.strip() == "108 条法条索引加载成功"


