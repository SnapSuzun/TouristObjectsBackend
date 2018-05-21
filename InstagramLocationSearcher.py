import hashlib

import requests
import re
import bs4
import json
from json import JSONDecodeError
import urllib.parse

from requests.exceptions import ChunkedEncodingError


class InstagramLocationSearch:
    instagram_root = "https://www.instagram.com"
    potential_query_ids = None
    previous_url = []
    current_url = None
    next_cursor = None
    nodes = None
    location_info = None
    rhx_gis = None
    csrf_token = None
    __session__ = None

    __attempts__ = 0

    def __init__(self, location):
        self.location = location
        self.__session__ = requests.Session()
        super().__init__()

    def __find(self):
        # Если добавить параметр __a=1, то будет json, при этом параметр max_id=next_cursor
        url_string = "https://www.instagram.com/explore/locations/%s/" % self.location
        response = bs4.BeautifulSoup(requests.get(url_string).text, "html.parser")
        self.potential_query_ids = self.get_query_id(response)
        shared_data = self.extract_shared_data(response)

        media = shared_data['entry_data']['LocationsPage'][0]['location']['media']
        self.nodes = media['nodes']
        self.next_cursor = media['page_info']['end_cursor']
        self.current_url = "https://www.instagram.com/explore/locations/%s/?__a=1" % self.location
        return self.nodes

    def new_next_nodes(self, count: int = None):
        if self.next_cursor is None:
            location = self.get_location_info()
            self.current_url = self.__prepare_url()
            self.next_cursor = location['media']['page_info']['end_cursor']
            return location['media']['nodes']
        elif not self.next_cursor:
            raise ValueError('Next cursor is empty')

        url = self.__prepare_url(self.next_cursor)
        data = requests.get(url).json()

        self.previous_url.append(self.current_url)
        self.current_url = url

        self.next_cursor = data['location']['media']['page_info']['end_cursor']
        self.nodes = data['location']['media']['nodes']
        if count:
            self.nodes = self.nodes[:count]
            self.next_cursor = self.nodes[-1]['id']
        return self.nodes

    def previous_nodes(self):
        if len(self.previous_url) == 0:
            raise ValueError("Previous url is not set")
        posts = []
        try:
            url = self.previous_url.pop()
            data = requests.get(url).json()
            if 'location' in data and 'media' in data['location']:
                self.current_url = url
                self.next_cursor = data['location']['media']['page_info']['end_cursor']
                posts = data['location']['media']['nodes']
            elif 'data' in data and 'location' in data['data']:
                data = data['data']
                self.current_url = url
                self.next_cursor = data['location']['edge_location_to_media']['page_info']['end_cursor']
                for edge in data['location']['edge_location_to_media']['edges']:
                    posts.append(edge['node'])
            else:
                raise ConnectionRefusedError()
        except:
            raise ConnectionRefusedError("Previous url is not available")
        self.nodes = posts
        return self.nodes

    def get_query_id(self, doc):
        query_ids = []
        for script in doc.find_all("script"):
            if script.has_attr("src") and (
                    "LocationPageContainer" in script['src'] or "TagPageContainer" in script['src']):
                text = requests.get("%s%s" % (self.instagram_root, script['src'])).text
                for query_id in re.findall("(?<=queryId:\")[0-9a-z]{32}", text):
                    query_ids.append(query_id)
        return query_ids

    def get_location_info(self):
        if self.location_info is None:
            url_string = self.__prepare_url()
            try:
                response = requests.get(url_string).json()
                self.location_info = response['graphql']['location']
            except:
                self.location_info = False
        return self.location_info

    def __prepare_url(self, max_id: int = None):
        return self.instagram_root + '/explore/locations/%s?__a=1&max_id=%s' % (
            self.location, str(max_id) if max_id else '')

    def get_location_media_count(self):
        location_info = self.get_location_info()
        if location_info is False:
            return 0
        return location_info['edge_location_to_media']['count']

    def get_location_coordinates(self):
        location_info = self.get_location_info()
        if location_info is False:
            return {}
        return {'latitude': location_info['lat'], 'longitude': location_info['lng']}

    def get_location_name(self):
        location_info = self.get_location_info()
        if location_info is False:
            return False
        return location_info['name']

    @staticmethod
    def extract_shared_data(doc):
        for script_tag in doc.find_all("script"):
            if script_tag.text.startswith("window._sharedData ="):
                shared_data = re.sub("^window\._sharedData = ", "", script_tag.text)
                shared_data = re.sub(";$", "", shared_data)
                shared_data = json.loads(shared_data)
                return shared_data

    def next_nodes(self, count=12):
        if self.next_cursor == "":
            return False

        # Здесь падает экзепшн ChunkedEncodingError
        try:
            if self.potential_query_ids is None:
                self.potential_query_ids = self.__get_potential_query_hash()
        except OSError:
            print('Can\'t get potential query ids')
            return []

        if self.potential_query_ids is None or len(self.potential_query_ids) == 0:
            raise ValueError("query_id is empty")

        wrong_query_ids = []
        success = False
        data = None
        url = None
        variables = {'id': self.location, 'first': count}
        if self.next_cursor is not None:
            variables['after'] = self.next_cursor
        for query_id in self.potential_query_ids:
            settings = {'params': urllib.parse.urlencode({'query_hash': query_id, 'variables': json.dumps(variables)})}
            settings['headers'] = {
                'X-Instagram-GIS': hashlib.md5('{0}:{1}'.format(
                    self.rhx_gis,
                    json.dumps(variables),
                ).encode('utf-8'),
                ).hexdigest(),
            }
            url = "https://www.instagram.com/graphql/query"
            try:
                response_text = self.__session__.get(url, **settings).text
                data = json.loads(response_text)
                if 'data' not in data or 'location' not in data['data']:
                    wrong_query_ids.append(query_id)
                    continue
                success = True
                data = data['data']
                break
            except JSONDecodeError as de:
                print(de)
                # no valid JSON retured, most likely wrong query_id resulting in 'Oops, an error occurred.'
                wrong_query_ids.append(query_id)
            except ChunkedEncodingError:
                return []
        for query_id in wrong_query_ids:
            self.potential_query_ids.remove(query_id)

        if not success:
            raise ValueError("existing query_ids is wrong")

        self.previous_url.append(self.current_url)
        self.current_url = url
        self.next_cursor = data['location']['edge_location_to_media']['page_info']['end_cursor']
        posts = []
        for edge in data['location']['edge_location_to_media']['edges']:
            posts.append(edge['node'])
        self.nodes = posts
        return self.nodes

    def __get_potential_query_hash(self):
        url_string = "https://www.instagram.com/explore/locations/%s/" % self.location
        response_text = requests.get(url_string).text

        try:
            match = re.search(
                r"<script[^>]*>\s*window._sharedData\s*=\s*((?!<script>).*)\s*;\s*</script>",
                response_text,
            )
            data = json.loads(match.group(1))
            if 'rhx_gis' in data:
                self.rhx_gis = data['rhx_gis']
            if 'csrf_token' in data['config']:
                self.csrf_token = data['config']['csrf_token']
        except (AttributeError, KeyError, ValueError):
            raise ValueError(url_string, response_text)

        response = bs4.BeautifulSoup(response_text, "html.parser")
        return self.get_query_id(response)
