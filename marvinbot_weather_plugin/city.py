import json
import os
import inspect
import Levenshtein

class City():
    def __init__(self):
        self.path = os.path.dirname(inspect.getfile(self.__class__))

    def getCity(self, name):
    	with open('{}/city.list.json'.format(self.path)) as file:
    		cities = json.load(file)

    		seen = set()
    		return [{'id' : city['id'], 'name': city['name'], 'country' : city['country']} 
    			for city in cities 
    				if Levenshtein.distance(city['name'].upper(), name.upper()) < 2 and city['country'] not in seen and not seen.add(city['country'])]