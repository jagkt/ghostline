import gevent
import greenswitch
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("ghostline.events")

FS_HOST = "127.0.0.1"
FS_PORT = 8021
FS_PASSWORD = "ClueCon"

WATCHED_EVENTS = ["CHANNEL_CREATE", "CHANNEL_ANSWER", "CHANNEL_HANGUP_COMPLETE"]


def on_event(event):
    name = event.headers.get("Event-Name", "UNKNOWN")
    uuid = event.headers.get("Unique-ID", "-")
    caller = event.headers.get("Caller-Caller-ID-Number", "-")
    dest = event.headers.get("Caller-Destination-Number", "-")
    logger.info("%s | uuid=%s caller=%s dest=%s", name, uuid, caller, dest)


def main():
    fs = greenswitch.InboundESL(host=FS_HOST, port=FS_PORT, password=FS_PASSWORD)
    fs.connect()
    logger.info("Connected and authenticated to FreeSWITCH ESL")

    # Client-side: what to do when each event arrives
    for event_name in WATCHED_EVENTS:
        fs.register_handle(event_name, on_event)

    # Server-side: tell FreeSWITCH to actually start sending these to us
    fs.send("event plain " + " ".join(WATCHED_EVENTS))
    logger.info("Subscribed to: %s", ", ".join(WATCHED_EVENTS))
    logger.info("Waiting for call events... (Ctrl+C to stop)")

    while True:
        gevent.sleep(1)


if __name__ == "__main__":
    main()
