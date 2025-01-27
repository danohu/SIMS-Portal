from flask import url_for, current_app, flash, redirect
from SIMS_Portal import db
from SIMS_Portal.models import User, Assignment, Emergency, NationalSociety
from slack_sdk import WebClient
import requests
import pandas as pd
import json
import os
import csv
import logging

def update_response_locations():
	"""
	Updates a CSV file with all countries' ISO3 codes and the count of emergencies to which SIMS has responded there.
	"""
	response_locations = db.engine.execute("SELECT iso3, count(*) AS count_location FROM nationalsociety JOIN emergency ON emergency_location_id = nationalsociety.ns_go_id GROUP BY iso3")
	
	list_of_location_dicts = []
	for location in response_locations:
		locations_dict = {}
		locations_dict['iso3'] = location[0]
		locations_dict['count'] = location[1]
		list_of_location_dicts.append(locations_dict)
	csv_file_path = "SIMS_Portal/static/data/emergencies_viz.csv"
	keys = ('iso3', 'count')
	with open(csv_file_path, 'w') as outfile:
		dict_writer = csv.DictWriter(outfile, keys)
		dict_writer.writeheader()
		dict_writer.writerows(list_of_location_dicts)
		outfile.close()
	
	current_app.logger.info('The update_response_locations function ran successfully.')
	
def update_active_response_locations():
	"""
	Updates a CSV file with all countries' ISO3 codes of active emergencies to which SIMS is currently responding.
	"""
	active_response_locations = db.engine.execute("SELECT * FROM emergency JOIN nationalsociety ON nationalsociety.ns_go_id = emergency.emergency_location_id WHERE emergency.emergency_status = 'Active'")
	
	list_of_location_dicts = []
	for location in active_response_locations:
		locations_dict = {}
		locations_dict['iso3'] = location.iso3
		locations_dict['count'] = 1
		list_of_location_dicts.append(locations_dict)
	csv_file_path = "SIMS_Portal/static/data/active_emergencies.csv"
	keys = ('iso3', 'count')
	with open(csv_file_path, 'w') as outfile:
		dict_writer = csv.DictWriter(outfile, keys)
		dict_writer.writeheader()
		dict_writer.writerows(list_of_location_dicts)
		outfile.close()
	
	current_app.logger.info('The update_active_response_locations function ran successfully.')
	
def get_trello_tasks(trello_board_url):
	"""
	Takes in a Trello board URL, isolates the Board ID, queries Trello for lists on that board called "To Do", then returns info for those cards.
	"""
	# isolate board ID from URL
	board_id = trello_board_url.split('/')[4]
	# insert board ID into query URL to grab all lists and their IDs from that board
	boards_url = "https://api.trello.com/1/boards/{}/lists".format(board_id)
	
	headers = {
		"Accept": "application/json"
	}
	
	query = {
		'key': os.environ.get('TRELLO_KEY'),
		'token': os.environ.get('TRELLO_TOKEN')
	}
	
	boards_response = requests.request(
		"GET",
		boards_url,
		headers=headers,
		params=query
	)
	# translate lists to legible format
	board_results = json.dumps(json.loads(boards_response.text), sort_keys=True, indent=4, separators=(",", ": "))
	
	# override incorrectly formatted booleans
	true = True
	false = False
	null = ''
	
	# get list ID that matches name "To Do"
	df_board_results = pd.DataFrame(eval(board_results))
	list_id = df_board_results.loc[df_board_results['name'] == 'To Do']
	str_id = list_id['id'].to_string(index=False)

	# send "To Do" list ID to API to get cards on list
	cards_url = "https://api.trello.com/1/lists/{}/cards".format(str_id)
	
	cards_response = requests.request(
	   "GET",
	   cards_url,
	   headers=headers,
	   params=query
	)
	# convert results to json
	cards_json = cards_response.json()
	
	# store list of dictionaries with relevant data
	card_info_list = []
	for card in cards_json:
		temp_dict = {}
		temp_dict['card_name'] = card['name']
		temp_dict['card_id'] = card['id']
		temp_dict['url'] = card['url']
		temp_dict['desc'] = card['desc']
		temp_dict['latest_activity'] = card['dateLastActivity'][:10]
		temp_dict['due'] = card['due']
		card_info_list.append(temp_dict)
	
	return card_info_list
		