# /proxy/proxy.py
# License: GPLv3 with Network Interface Clause

"""
Proxy is meant to communicate with a Faraday Radio over USB UART via a serial
port. It has a thread which continuously checks for data over USB and places it
into a thread safe dequeue. The Flask server returns requested data from this
queue with a GET request or adds to it with a POST request via an IP address
and port specified in the configuration file proxy.ini.
"""

import time
import base64
import json
import logging
import logging.config
import threading
import ConfigParser
import os
from collections import deque

from flask import Flask
from flask import request

from faraday_uart_stack import layer_4_service

# Start logging after importing modules
filename = os.path.abspath("loggingConfig.ini")
logging.config.fileConfig(filename)
logger = logging.getLogger('Proxy')

# Load Proxy Configuration from proxy.ini file
proxyConfig = ConfigParser.RawConfigParser()
filename = os.path.abspath("proxy.ini")
proxyConfig.read(filename)

# Create and initialize dictionary queues
postDict = {}
postDicts = {}
getDicts = {}
unitDict = {}


def uart_worker(modem, getDicts, units):
    """
    Interface Faraday ports over USB UART

    This function interfaces the USB UART serial data with an infinit loop
    that checks all Faraday "ports" for data and appends/pops data from
    queues for send and receive directions.
    """
    logger.info('Starting uart_worker thread')

    # Iterate through dictionary of each unit in the dictionary creating a
    # deque for each item
    for key, values in units.iteritems():
        postDicts[str(values["callsign"]) + "-" + str(values["nodeid"])] = {}
        getDicts[str(values["callsign"]) + "-" + str(values["nodeid"])] = {}

    # Loop through each unit checking for data, if True place into deque
    while(1):
        # Place data into the FIFO coming from UART
        for unit, com in modem.iteritems():
            try:
                for port in range(0, 255):
                    if(com.RxPortHasItem(port)):
                        # Data is available
                        # convert to BASE64 and place in queue
                        item = {}
                        item["data"] = base64.b64encode(com.GET(port))
                        # Use new buffers
                        try:
                            getDicts[unit][port].append(item)
                        except:
                            getDicts[unit][port] = deque([], maxlen=100)
                            getDicts[unit][port].append(item)

            except StandardError as e:
                logger.error("StandardError: " + str(e))
            except ValueError as e:
                logger.error("ValueError: " + str(e))
            except IndexError as e:
                logger.error("IndexError: " + str(e))
            except KeyError as e:
                logger.error("KeyError: " + str(e))

            time.sleep(0.001)
            # Check for data in the POST FIFO queue. This needs to check for
            # COM ports and create the necessary buffers on the fly
            for port in range(0, 255):
                try:
                    count = len(postDicts[unit][port])
                except:
                    # Port simply doesn't exist so don't bother
                    pass
                else:
                    for num in range(count):
                        # Data is available, pop off [unit][port] queue
                        # and convert to BASE64 before sending to UART
                        message = postDicts[unit][port].popleft()
                        message = base64.b64decode(message)
                        com.POST(port, len(message), message)

            # Slow down while loop to something reasonable
            time.sleep(0.001)


# Initialize Flask microframework
app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def proxy():
    """
    Provides a RESTful interface to the USB UART on localhost '/'

    Starts a flask server on port 8000 (default) which serves data from the
    requested Faraday port on localhost URL "/". This simple server is the
    intermediary between the USB UART of a Faraday radio and software
    applications. All data is transferred to the localhost as BASE64 packets in
    JSON dictionaries while all data tranferred over USB UART is converted to
    raw bytes.
    """
    if request.method == "POST":
        try:
            data = request.get_json(force=False)  # Requires HTTP JSON header
            port = request.args.get("port")
            callsign = request.args.get("callsign").upper()
            nodeid = request.args.get("nodeid")

            # Check for parameters and ensure all required are present and of
            # acceptable values

            if port is None:
                # Required
                raise StandardError("Missing 'port' parameter")
            else:
                # Ensure port value is an Integer
                port = int(port)
                # Check to see if the port is in the valid range
                if port > 255 or port < 0:
                    raise ValueError(
                        "Faraday Ports valid integer between 0-255")

            if callsign is None:
                # Required
                raise StandardError("Missing 'callsign' parameter")
            else:
                # Ensure callsign value is a string
                callsign = str(callsign)

            if nodeid is None:
                # Required
                raise StandardError("Missing 'nodeid' parameter")
            else:
                nodeid = int(nodeid)
                # Check to see if the Node ID is in the valid range
                if nodeid > 255 or nodeid < 0:
                    raise ValueError(
                        "Faraday Node ID's valid integer between 0-255")

        except ValueError as e:
            logger.error("ValueError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except IndexError as e:
            logger.error("IndexError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except KeyError as e:
            logger.error("KeyError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except StandardError as e:
            logger.error("StandardError: " + str(e))
            return json.dumps({"error": str(e)}), 400

        # Create station name and check for presents of postDicts queue.
        # Error if not present since this means unit not in proxy.ini configs
        station = callsign + "-" + str(nodeid)
        try:
            postDicts[station]
        except KeyError as e:
            logger.error("KeyError: " + str(e))
            return json.dumps({"error": str(e)}), 400

        # Iterate through items in the data["data"] array. If port isn't
        # present, create port queue for it and append data to that queue
        try:
            data["data"]
        except:
            logger.error("Error: No 'data' key in dictionary")
            return json.dumps(
                {"error": "Error: No 'data' key in dictionary"}), 400
        else:
            total = len(data["data"])
            print "length:", total
            sent = 0
            for item in data['data']:
                try:
                    postDicts[station][port].append(item)
                except:
                    postDicts[station][port] = deque([], maxlen=100)
                    postDicts[station][port].append(item)
                sent += 1
            return json.dumps(
                {"status": "Posted {0} of {1} Packet(s)"
                    .format(sent, total)}), 200

    else:
        # This is the GET routine to return data to the user
        try:
            port = request.args.get("port")
            limit = request.args.get("limit", 100)
            callsign = request.args.get("callsign").upper()
            nodeid = request.args.get("nodeid")

        except ValueError as e:
            logger.error("ValueError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except IndexError as e:
            logger.error("IndexError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except KeyError as e:
            logger.error("KeyError: " + str(e))
            return json.dumps({"error": str(e)}), 400

        # Check to see that required parameters are present
        try:
            if port is None:
                # Required
                raise StandardError("Missing 'port' parameter")
            else:
                # Ensure port value is an Integer
                port = int(port)
                # Check to see if the port is in the valid range
                if port > 255 or port < 0:
                    raise ValueError(
                        "Faraday Ports valid integer between 0-255")
            if callsign is None:
                # Required
                raise StandardError("Missing 'callsign' parameter")
            else:
                # Ensure callsign value is a string
                callsign = str(callsign)
            if nodeid is None:
                # Required
                raise StandardError("Missing 'nodeid' parameter")
            else:
                nodeid = int(nodeid)
                # Check to see if the Node ID is in the valid range
                if nodeid > 255 or nodeid < 0:
                    raise ValueError(
                        "Faraday Node ID's valid integer between 0-255")

            # Make sure port exists before checking it's contents and length
            station = callsign + "-" + str(nodeid)
            try:
                getDicts[station][port]
            except KeyError as e:
                message = "KeyError: " +\
                     "Callsign '{0}' or Port '{1}' does not exist"\
                     .format(station, port)
                logger.error(message)
                return json.dumps({"error": message}), 400

            if limit is None:
                # Optional
                limit = len(getDicts[station][port])
            else:
                limit = int(limit)
                # Check for less than or equal to zero case
                if limit <= 0:
                    message = "Error: Limit '{0}' is invalid".format(limit)
                    return json.dumps({"error": message}), 400

        except ValueError as e:
            logger.error("ValueError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except IndexError as e:
            logger.error("IndexError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except KeyError as e:
            logger.error("KeyError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except StandardError as e:
            logger.error("StandardError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        # Return data from queue to RESTapi
        # If data is in port queu, turn it into JSON and return
        try:
            if (len(getDicts[callsign + "-" + str(nodeid)][port]) > 0):
                data = []
                while getDicts[callsign + "-" + str(nodeid)][port]:
                    packet = \
                        getDicts[
                            callsign + "-" + str(nodeid)][port].popleft()
                    data.append(packet)
                    if len(data) >= limit:
                        break

                return json.dumps(data, indent=1), 200,\
                    {'Content-Type': 'application/json'}
            else:
                # No data in service port, but port is being used
                logger.info("Empty buffer for port %d", port)
                return '', 204  # HTTP 204 response cannot have message data

        except ValueError as e:
            logger.error("ValueError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except IndexError as e:
            logger.error("IndexError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except KeyError as e:
            logger.error("KeyError: " + str(e))
            return json.dumps({"error": str(e)}), 400
        except StandardError as e:
            logger.error("StandardError: " + str(e))
            return json.dumps({"error": str(e)}), 400


@app.errorhandler(404)
def pageNotFound(error):
    """HTTP 404 response for incorrect URL"""
    logger.error("Error: " + str(error))
    return json.dumps({"error": "HTTP " + str(error)}), 404


def callsign2COM():
    """ Associate configuration callsigns with serial COM ports"""
    local = {}
    num = int(proxyConfig.get('PROXY', 'units'))
    units = range(0, num)

    for unit in units:
        # TODO We don't really check for valid input here yet
        item = "UNIT" + str(unit)
        callsign = proxyConfig.get(item, "callsign").upper()
        nodeid = proxyConfig.get(item, "nodeid")
        com = proxyConfig.get(item, "com")
        baudrate = proxyConfig.getint(item, "baudrate")
        timeout = proxyConfig.getint(item, "timeout")
        local[str(item)] =\
            {
            "callsign": callsign,
            "nodeid": nodeid,
            "com": com,
            "baudrate": baudrate,
            "timeout": timeout
            }

    local = json.dumps(local)
    return json.loads(local)


def main():
    """Main function which starts UART Worker thread + Flask server."""
    logger.info('Starting proxy server')

    # Associate serial ports with callsigns
    # global units
    units = callsign2COM()

    # Initialize local variables
    threads = []

    while(1):
        # Initialize a Faraday Radio device
        try:
            for key, values in units.iteritems():
                unitDict[str(values["callsign"] + "-" + values["nodeid"])] =\
                    layer_4_service.faraday_uart_object(
                        str(values["com"]),
                        int(values["baudrate"]),
                        int(values["timeout"]))
            logger.info("Connected to Faraday")
            break

        except StandardError as e:
            logger.error("StandardError: " + str(e))
            time.sleep(1)
        except ValueError as e:
            logger.error("ValueError: " + str(e))
            time.sleep(1)
        except IndexError as e:
            logger.error("IndexError: " + str(e))
            time.sleep(1)
        except KeyError as e:
            logger.error("KeyError: " + str(e))
            time.sleep(1)

    t = threading.Thread(target=uart_worker, args=(unitDict, getDicts, units))
    threads.append(t)
    t.start()

    # Start the flask server on localhost:8000
    proxyHost = proxyConfig.get("FLASK", "host")
    proxyPort = proxyConfig.getint("FLASK", "port")

    app.run(host=proxyHost, port=proxyPort, threaded=True)


if __name__ == '__main__':
    main()
