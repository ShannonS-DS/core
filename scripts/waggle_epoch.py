#!/usr/bin/env python3

import os
import sys
import time
import datetime
import subprocess
import json
import logging
import urllib.request, urllib.error, urllib.parse

"""
    This module keeps the current time using outer sources such as beehive server or nodecontroller. To get time from beehive server this uses html request. If it does not work (e.g., no internet) the module tries to get time from connected nodecontroller.
    The update happens periodically (e.g., everyday).
"""

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_host(file):
	try:
		f = open(file, 'r')
		data = f.read().strip()
		f.close()
		return data
	except:
		return ""

def get_time_from_beehive(host):
	"""
		Tries to get data from beehive server. It retries NUM_OF_RETRY with a delay of 10 sec.
	"""
	if host == "":
		logging.info("Beehive host not present")
		return None

	logging.info("Attemping getting time from %s" % host)

	URL = "http://%s/api/1/epoch" % host
	NUM_OF_RETRY=5
	t = None
	error = ""
	for n in range(NUM_OF_RETRY):
		try:
			response = urllib.request.urlopen(URL, timeout=10)
			msg = json.loads(response.read().decode())
			t = msg['epoch']
			logging.info("Got time from %s: %s" % (URL, msg))
			break
		except Exception as e:
			t = None
			error = str(e)
			time.sleep(10)

	if t == None:
		logging.info("Failed to get time from the server: %s" % error)

	return t

def get_time_from_nc(address):
	if address == "":
		logging.info("Nodecontroller host not present")
		return None

	logging.info("Attemping getting time from %s" % address)
	HOST = address
	NUM_OF_RETRY=3
	CMD = "ssh -i /usr/lib/waggle/SSL/guest/id_rsa_waggle_aot_guest_node \
			-o \"StrictHostKeyChecking no\" -o \"ConnectTimeout 2\" \
			waggle@%s" % HOST
	CMD += " -x date +%s"
	t = None
	error = ""
	for n in range(NUM_OF_RETRY):
		try:
			response = subprocess.getoutput(CMD)
			t = response
			logging.info("Got time from %s:%s" % (HOST, t))
			break
		except Exception as e:
			t = None
			error = str(e)
			time.sleep(10)

	if t == None:
		logging.info("Failed to get time from NC:%s", error)
	return t

def set_time_wagman(t):
	time_i = int(t)
	CMD = "wagman-client epoch"
	DIFF = 60 # 1 minute tolerance
	error = ""
	NUM_OF_RETRY = 3
	for n in range(NUM_OF_RETRY):
		try:
			wagman_time = subprocess.getoutput(CMD)
			wagman_time = int(wagman_time)
			if abs(time_i - wagman_time) > DIFF:
				logging.info("Wagman time needs to be updated to %d" % t)
				date = time.strftime("%Y %m %d %H %M %S", time.gmtime(t))
				CMD = "wagman-client date %s" % date
				subprocess.getoutput(CMD)
				logging.info("Wagman time updated")
			return
		except Exception as e:
			time.sleep(10)
			error = str(e)

	logging.info("Could not update wagman time: %s" % error)


logging.info("waggl-epoch service started")

BEEHIVE_HOST = get_host('/etc/waggle/server_host')
model = subprocess.getoutput("head -n 1 /media/boot/boot.ini | cut -d '-' -f 1 | tr -d '\n'")

if "ODROIDC" in model:
	NODE_CONTROLLER_IP = ""
else:
	NODE_CONTROLLER_IP = get_host('/etc/waggle/node_controller_host')

a_day = 86400
SLEEP_WAIT = 10 # 10 seconds
current_time = time.time()
next_period = current_time - a_day

while True:
	current_time = time.time()
	if next_period < current_time:
		logging.info("current time: %s, update needed" % (current_time))
		# Try to get time from NC
		d = get_time_from_beehive(BEEHIVE_HOST)
		if not d:
			d = get_time_from_nc(NODE_CONTROLLER_IP)

		if not d:
			time.sleep(SLEEP_WAIT)
			continue
		else:
			try:
				subprocess.call(["date", "-s@%s" % (d)])
			except Exception as e:
				time.sleep(SLEEP_WAIT)
				logging.info("Failed to set time:%s", (str(e)))
				continue

		# Set next update
		current_time = time.time()
		next_period = current_time + a_day
		logging.info("Next time-update will be at around %d" % next_period)

		# Set Wagman time if needed
		if "ODROIDC" in model:
			set_time_wagman(current_time)

	time.sleep(60)