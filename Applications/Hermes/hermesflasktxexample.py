import requests
import base64
import cPickle
import time



def main():
    while 1:
        message = raw_input("Enter Message:")
        payload = {'localcallsign': 'kb1lqd', 'localnodeid': 1, 'destinationcallsign': 'kb1lqd', 'destinationnodeid': 2, 'data': message}
        txdata = requests.post('http://127.0.0.1:8005/', params=payload)

if __name__ == '__main__':
    main()


