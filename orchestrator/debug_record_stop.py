import gevent
import greenswitch
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
logger = logging.getLogger("debug")

def on_event(event):
    logger.info(f"RECORD_STOP headers: %s", dict(event.headers))
    
def main():
    fs = greenswitch.InboundESL(host="127.0.01", port=8021, password="ClueCon")
    fs.connect()
    fs.register_handle("RECORD_STOP", on_event)
    fs.send("event plain RECORD_STOP")
    logger.info("Waiting for a call to 7000")
    while True:
        gevent.sleep(1)


if __name__ == "__main__":
    main()
