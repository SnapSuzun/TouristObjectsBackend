from json import JSONDecodeError

import requests
import json

from facebook.Models import Place
import configparser
import os.path
import urllib.parse


class FacebookAPI:
    __CONFIGURATION_FILENAME__ = 'facebook.ini'
    __CONFIGURATION_SECTION__ = 'Facebook'

    __API_ROOT_URL__ = 'https://graph.facebook.com'

    __app_id__ = None
    __app_secret__ = None

    def __init__(self):
        self.__load_config__()

    def query(self, path: str, params: dict = None):
        url = urllib.parse.urljoin(self.__API_ROOT_URL__, path)
        if params is None:
            params = {}
        if 'access_token' not in params:
            params['access_token'] = "{0}|{1}".format(self.__app_id__, self.__app_secret__)
        # request_params = ''
        # if params is not None:
        #     request_params = urllib.parse.urlencode(params)
        # url += '?' + request_params

        response = requests.get(url, params)
        try:
            decoded_response = response.json()
        except JSONDecodeError:
            print('Server return not json answer')
            decoded_response = {}

        if response.status_code != 200:
            error_message = None
            decoded_response = response.json()
            if 'error' in decoded_response and 'message' in decoded_response['error']:
                error_message = decoded_response['error']['message']
            raise ConnectionError(
                'Server return response with code {0}. Error: {1}'.format(response.status_code, error_message))
        return decoded_response

    def __load_config__(self):
        path = os.path.join(os.path.dirname(__file__), self.__CONFIGURATION_FILENAME__)
        if not os.path.isfile(path):
            raise FileNotFoundError("Configuration file '{0}' not found.".format(path))
        config = configparser.ConfigParser()
        config.read(path)
        if self.__CONFIGURATION_SECTION__ not in config:
            raise KeyError("Section '{0}' not found in configuration file.".format(self.__CONFIGURATION_SECTION__))
        if 'AppId' not in config[self.__CONFIGURATION_SECTION__]:
            raise KeyError("Property 'AppId' not found in section '{0}'".format(self.__CONFIGURATION_SECTION__))
        if 'AppSecret' not in config[self.__CONFIGURATION_SECTION__]:
            raise KeyError("Property 'AppSecret' not found in section '{0}'".format(self.__CONFIGURATION_SECTION__))
        self.__app_id__ = config[self.__CONFIGURATION_SECTION__]['AppId']
        self.__app_secret__ = config[self.__CONFIGURATION_SECTION__]['AppSecret']


class PlaceSearcherForLocation:
    location_id = None
    cursor = None

    def __init__(self, location_id):
        self.location_id = location_id

    def next(self):
        query = "%s/places-in" % str(self.location_id)
        request_data = {'query': query, 'original_query': query, '__a': 1}
        if self.cursor is not None:
            request_data['cursor'] = self.cursor
        url = 'https://www.facebook.com/browse/async/places/?dpr=1'
        data = requests.post(url, request_data).text
        data = json.loads(data.replace('for (;;);', ''))
        data = data['payload']
        places = []

        if 'results' in data:
            places = self.__convert_places__(data['results'])
        if 'hasNextPage' in data and data['hasNextPage']:
            self.cursor = data['pagingOptions']['cursor']
        else:
            self.cursor = False
        return places

    def __convert_places__(self, data: dict):
        places = []
        for place_id in data:
            place_info = data[place_id]['entityInfo']
            name = None
            category = None
            latitude = None
            longitude = None
            if 'mapInfo' in place_info and place_info['mapInfo'] is not None:
                latitude = place_info['mapInfo']['lat']
                longitude = place_info['mapInfo']['long']
            if 'aboutInfo' in place_info and place_info['aboutInfo'] is not None:
                category = place_info['aboutInfo']['category']
                name = place_info['aboutInfo']['name']
            places.append(
                Place.create(uid=place_id, name=name, category=category, latitude=latitude, longitude=longitude))
        return places


class PlaceSearcherByCoordinates(FacebookAPI):
    CATEGORY_FOOD_BEVERAGE = 'FOOD_BEVERAGE'
    CATEGORY_ARTS_ENTERTAINMENT = 'ARTS_ENTERTAINMENT'
    CATEGORY_EDUCATION = 'EDUCATION'
    CATEGORY_FITNESS_RECREATION = 'FITNESS_RECREATION'
    CATEGORY_HOTEL_LODGING = 'HOTEL_LODGING'
    CATEGORY_MEDICAL_HEALTH = 'MEDICAL_HEALTH'
    CATEGORY_SHOPPING_RETAIL = 'SHOPPING_RETAIL'
    CATEGORY_TRAVEL_TRANSPORTATION = 'TRAVEL_TRANSPORTATION'

    __latitude__ = None
    __longitude__ = None
    __distance__ = None
    __query__ = None
    __fields__ = None
    __categories__ = None

    __previous_cursor__ = None
    __next_cursor__ = None

    def __init__(self, latitude: float = None, longitude: float = None, distance: int = 200000, query: str = None,
                 fields: list = None, categories: list = None, next_cursor: str = None):
        if (longitude is None or latitude is None or distance is None) and query is None:
            raise ValueError('Query or center coordinates and distance should be set')

        self.__latitude__ = latitude
        self.__longitude__ = longitude
        self.__distance__ = distance
        self.__query__ = query
        self.__fields__ = fields
        self.__categories__ = categories
        self.__previous_cursor__ = []
        self.__next_cursor__ = next_cursor
        super().__init__()

    def next(self):
        if self.__next_cursor__ is False:
            return False

        places, paging = self.__search_places__(self.__next_cursor__)
        self.__previous_cursor__.append(self.__next_cursor__)
        if paging and 'cursors' in paging and 'after' in paging['cursors']:
            self.__next_cursor__ = paging['cursors']['after']
        else:
            self.__next_cursor__ = False
        return self.__convert_places(places), self.__next_cursor__

    def prev(self):
        if not self.__previous_cursor__:
            return False
        places, paging = self.__search_places__(self.__previous_cursor__.pop())
        if paging and 'cursors' in paging and 'after' in paging['cursors']:
            self.__next_cursor__ = paging['cursors']['after']
        else:
            self.__next_cursor__ = False
        return self.__convert_places(places), self.__next_cursor__

    def __search_places__(self, cursor: str = None):
        params = {'type': 'place'}
        if self.__latitude__ is not None and self.__longitude__ is not None:
            params['center'] = "{0},{1}".format(self.__latitude__, self.__longitude__)
        if self.__distance__ is not None:
            params['distance'] = self.__distance__
        if self.__query__ is not None:
            params['query'] = self.__query__
        if self.__fields__ is not None and len(self.__fields__) > 0:
            params['fields'] = ','.join(self.__fields__)
        if self.__categories__ is not None and len(self.__categories__) > 0:
            params['categories'] = json.dumps(self.__categories__)

        if cursor is not None:
            params['after'] = cursor

        response = self.query('search', params)

        paging = None
        if 'paging' in response:
            paging = response['paging']
        return response['data'], paging

    def __convert_places(self, data: list):
        places = []
        for item in data:
            places.append(Place.create(uid=item['id'], name=item['name'], category=item['category'],
                                       latitude=item['location']['latitude'], longitude=item['location']['longitude']))
        return places
