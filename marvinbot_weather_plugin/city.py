# -*- coding: utf-8 -*-

import json
import os
import Levenshtein

def getCity(name):
	with open('{}/city.list.json'.format(os.path.dirname(__file__)), encoding='utf-8') as file:
		cities = json.load(file)

		seen = set()
		return [{'id' : city['id'], 'name': city['name'], 'country' : city['country']} 
			for city in cities 
				if Levenshtein.distance(city['name'].upper(), name.upper()) < 2 and city['country'] not in seen and not seen.add(city['country'])]