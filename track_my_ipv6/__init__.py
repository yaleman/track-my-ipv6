""" tracks interface ipv6 addresses over time, helpful for troubleshooting dumb

    uses splunklogger from github.com/yaleman/splunkhec/
    also click, loguru, tinydb, ifcfg
"""

import json
import sys
from pathlib import Path
from time import time, sleep
from typing import Any, Dict, Optional

try:
    import ifcfg # type: ignore
    import click
    from loguru import logger
    from tinydb import TinyDB, Query

    from splunk_http_event_collector import http_event_collector # type: ignore
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
                        logmsg = json.dumps({
                            "message":"New address found",
                            "interface": name,
                            "address" : address,
                            "mac" : ether,
                        })
                        logger.info(logmsg)
                        found_new_address = True
                if not found_new_address:
                    logger.debug("No new interfaces found")

class SplunkLogger:
    """ logs through hec """
    def __init__(self, config: Dict[str, str]) -> None:
        self.logger  = http_event_collector(
            token=config["splunk_token"],
            http_event_server=config["splunk_host"],
            http_event_port=config.get("splunk_port", 443),
            http_event_server_ssl=True,

        )
        self.logger.SSL_verify=True
        self.logger.sourcetype = config["splunk_sourcetype"]
        self.logger.index = config["splunk_index"]

    def send(
        self,
        message: Any,
        ) -> None:
        """ sends a message to splunk """
        payload = {
            "event" : {
                "log_level" : message.record["level"].name,
            }
        }
        try:
            payload["event"].update(json.loads(message.record["message"]))
        except json.JSONDecodeError as error:
            print(f"no json here... {error} - {message.record['message']}")
            payload["event"]  = message.record["message"]
        self.logger.sendEvent(
            payload=payload,
            eventtime=message.record["time"].strftime("%s"),
            )

    def __del__(self) -> None:
        """ flush queue before quitting """
        self.logger.flushBatch()


def load_config(config_path: str) -> Optional[Dict[str,str]]:
    """ loads config """
    config_file = Path(config_path).expanduser().resolve()
    if not config_file.exists():
        logger.warning("Can't find config file ({}), disabling splunk logging", config_file)
        return None
    with config_file.open(encoding="utf-8") as file_handle:
        try:
            result: Dict[str,str] = json.load(file_handle)
            return result
        except json.JSONDecodeError as jsonerror:
            logger.error("Failed to parse config file, disabling splunk logging: {}", jsonerror)
    return None


@click.command()
@click.option("--disable-splunk", is_flag=True, default=False)
@click.option("--oneshot", is_flag=True, default=False)
@click.option("--config", "-c", default="track-my-ipv6.json", help="Configuration file path.")
def cli(
    disable_splunk: bool=False,
    config: str="track-my-ipv6.json",
    oneshot: bool=False,
    ) -> None:
    """ command line interface """

    configuration = load_config(config)

    if not disable_splunk and configuration is not None:
        splunklogger = SplunkLogger(configuration)

        logger.add(splunklogger.send,
                format="{message}",
                serialize=True,
                colorize=False,
                level="INFO",
                )

    database = TinyDB('./database.db')

    while True:
        do_run(database)
        if oneshot:
            break
        logger.debug("Sleeping for {} seconds...", SLEEP_TIME)
        sleep(SLEEP_TIME)
