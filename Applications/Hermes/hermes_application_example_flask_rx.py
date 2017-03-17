import os
import time
import hermesobject as hermesobject
import ConfigParser
import logging.config
import sys
import json
import base64
import cPickle

from flask import Flask
from flask import request

#Open configuration INI
config = ConfigParser.RawConfigParser()
filename = os.path.abspath("hermes.ini")
config.read(filename)

#Definitions

#Variables
transmitter_device_callsign = config.get("DEVICES", "UNIT0CALL") # Should match the connected Faraday unit as assigned in Proxy configuration
transmitter_device_node_id = config.getint("DEVICES", "UNIT0ID") # Should match the connected Faraday unit as assigned in Proxy configuration
transmitter_device_callsign = str(transmitter_device_callsign).upper()
receiver_device_callsign = config.get("DEVICES", "UNIT1CALL") # Should match the programmed callsign of the remote Faraday device to be commanded (receive)
receiver_device_node_id = config.getint("DEVICES", "UNIT1ID") # Should match the programmed callsign of the remote Faraday device to be commanded (receive)
receiver_device_callsign = str(receiver_device_callsign).upper()


# Create messaging unit objects with the two device connected to local proxy
receiver = hermesobject.MessageObject(receiver_device_callsign, receiver_device_node_id)


# Initialize Flask microframework
app = Flask(__name__)

@app.route('/', methods=['GET'])
def getMessage():
    if request.method == "POST":
        return False
    else:
        return "Hello!"

def main():
    """Main function which starts the Flask server."""

    #Get INI file configuration for Flask server
    config_host = config.get("FLASK", "HOST")
    config_port = config.get("FLASK", "PORT")

    # Start the flask server on localhost:8001
    hermesHost = config_host
    hermesPort = config_port


    app.run(host=hermesHost, port=hermesPort, threaded=True)

if __name__ == '__main__':
    main()
