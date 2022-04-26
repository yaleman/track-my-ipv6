""" tests it """


from click.testing import CliRunner

from track_my_ipv6 import cli

def test_nothing() -> None:
    """doesn't test anything"""


    client = CliRunner()

    result = client.invoke(cli, ["-c", "asdfasdfsadfdf", "--oneshot"])
    print(result)
    assert result.return_value is None
