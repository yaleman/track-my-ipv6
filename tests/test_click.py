""" testing click functionality """

from click.testing import CliRunner
from track_my_ipv6 import cli

def test_command_help() -> None:
    """ test that something works using click """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--disable-splunk",
            "-c",
            "/dev/null",
            "--oneshot",
        ],
        )
    assert result.exit_code == 0
    print(result)
