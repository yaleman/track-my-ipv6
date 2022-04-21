""" tracks interface ipv6 addresses over time, helpful for troubleshooting dumb

    uses splunklogger from github.com/yaleman/splunkhec/
    also click, loguru, tinydb, ifcfg
"""

from time import time, sleep
import sys

try:
    import ifcfg # type: ignore
    import click
    from loguru import logger
    from tinydb import TinyDB, Query
    from splunklogger import SplunkLogger, setup_logging

    from config import SPLUNK_HEC_HOST, SPLUNK_HEC_TOKEN, SPLUNK_SOURCETYPE, SPLUNK_INDEX
except ImportError as error_message:
    print(f"Failed to import {error_message.name}, bailing. Error: {error_message}")
    sys.exit(1)

SLEEP_TIME = 5
STORE_TIME = (24 * 3600) # 1 day


def do_run(db_object: TinyDB) -> None:
    """ does a single data processing run """
    storedaddress = Query()
    earliest_timestamp = time() - STORE_TIME
    db_object.remove(storedaddress.timestamp < STORE_TIME)
    for name, interface in list(ifcfg.interfaces().items()):
        printed_interface = False
        found_new_address = False
        # do something with interface
        if name.startswith("en"):
            if interface.get("inet6"):
                for address in interface.get("inet6"):
                    if address.startswith('fe80'):
                        logger.debug("Skipping {}, is link-local", address)
                        continue
                    if not printed_interface:
                        logger.debug("Checking {}", name)
                        printed_interface = True
                    if len(db_object.search((storedaddress.address == address) & \
                                    (storedaddress.timestamp >= earliest_timestamp) )) == 0:
                        ether = interface.get('ether')
                        db_object.insert({
                            "timestamp" : int(time()),
                            "address" : address,
                            "ether" : ether,
                            "interface" : name,
                            })
                        logmsg = "message=\"New address found\" interface=\"{}\" address=\"{}\" mac=\"{}\"" # pylint: disable
                        logger.info(logmsg, name, address, ether)
                        found_new_address = True
                if not found_new_address:
                    logger.debug("No new interfaces found")


@click.command()
@click.option('--debug','-d',is_flag=True, default=False)
def cli(debug: bool=False) -> None:
    """ command line interface """


    splunklogger = SplunkLogger(endpoint=f"https://{SPLUNK_HEC_HOST}/services/collector",
                                token=SPLUNK_HEC_TOKEN,
                                sourcetype=SPLUNK_SOURCETYPE,
                                index_name=SPLUNK_INDEX,
                                )
    logger.add(splunklogger.splunk_logger,
            format="{message}",
            serialize=False,
            colorize=False,
            )
    setup_logging(logger, debug, use_default_loguru=False)

    database = TinyDB('./database.db')
    while True:
        do_run(database)
        logger.debug("Sleeping for {} seconds...", SLEEP_TIME)
        sleep(SLEEP_TIME)
