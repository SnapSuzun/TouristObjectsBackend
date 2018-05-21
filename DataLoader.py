from facebook import Facebook
from facebook import Models
import time

from InstagramLocationSearcher import InstagramLocationSearch
from MongoDB import MongoDB
from random import randint
import os
import requests
import multiprocessing.pool
import bson.objectid


class DataLoader:

    @staticmethod
    def search_places_for_location(location_id, limit: int = None, cursor=None):
        searcher = Facebook.PlaceSearcherForLocation(location_id)
        if cursor is not None:
            searcher.cursor = cursor
        places = {}
        while searcher.cursor is not False:
            found_places = searcher.next()
            for place in found_places:
                places[place.uid] = place.__dict__
            if limit is not None and len(places) >= limit:
                break
            time.sleep(randint(3, 5))
        return places, searcher.cursor

    def load_places_for_city(self, city_id: int = None, limit: int = None, use_last_cursor: bool = False):
        collection = MongoDB.db()['cities']
        placesCollection = MongoDB.db()['places']
        query = {}
        if city_id is not None:
            query['city_id'] = city_id
        for city in collection.find(query):
            cursor = None
            if use_last_cursor and 'last_cursor' in city:
                if city['last_cursor'] is False:
                    continue
                cursor = city['last_cursor']
            print('Start searching places for %s' % city['name'])
            counter = 0
            while limit is None or counter < limit:
                places, cursor = self.search_places_for_location(city['uid'], 10, cursor)
                for place_id in places:
                    if not placesCollection.find_one({'uid': place_id}):
                        place = places[place_id]
                        place['city_id'] = city['_id']
                        place['location'] = {'type': 'Point', 'coordinates': [place['longitude'], place['latitude']]}
                        placesCollection.insert_one(place)
                        print("Place `%s` was added to `%s`" % (place['name'], city['city_local_name']))
                        counter += 1
                MongoDB.db()['cities'].update_one({
                    '_id': city['_id']
                }, {
                    '$set': {
                        'last_cursor': cursor
                    }
                })
                print('Found %d places of %d' % (counter, limit if limit is not None else -1))
                if cursor is False:
                    break

    @staticmethod
    def search_places_for_city(city_id: str = None, limit: int = None, use_last_cursor: bool = True):
        cursor_property = 'places_search_cursor'
        city_collection = MongoDB.db()['cities']
        places_collection = MongoDB.db()['places']
        query = {}

        if city_id is not None:
            query['_id'] = bson.objectid.ObjectId(city_id)

        for city in city_collection.find(query):
            cursor = None
            if use_last_cursor and cursor_property in city:
                if city[cursor_property] is False:
                    continue
                cursor = city[cursor_property]
            print('Start searching places for %s' % city['name'])
            counter = 0
            searcher = Facebook.PlaceSearcherByCoordinates(latitude=city['latitude'], longitude=city['longitude'],
                                                           distance=20000,
                                                           fields=['name', 'location', 'category'], next_cursor=cursor,
                                                           categories=[
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_ARTS_ENTERTAINMENT,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_EDUCATION,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_FITNESS_RECREATION,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_HOTEL_LODGING,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_MEDICAL_HEALTH,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_SHOPPING_RETAIL,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_TRAVEL_TRANSPORTATION,
                                                               Facebook.PlaceSearcherByCoordinates.CATEGORY_FOOD_BEVERAGE
                                                           ])
            while limit is None or counter < limit:
                places, cursor = searcher.next()
                for place in places:
                    if not places_collection.find_one({'uid': place.uid}):
                        place_city_id = city['_id']
                        if place.is_city():
                            place_city = city_collection.find_one({'uid': place.uid})
                            if not place_city:
                                place_city_id = city_collection.insert_one({
                                    'city_id': place.uid,
                                    'uid': place.uid,
                                    'name': place.name,
                                    'city_local_name': place.name,
                                    'latitude': place.latitude,
                                    'longitude': place.longitude
                                }).inserted_id
                            else:
                                place_city_id = place_city['_id']
                        place = place.__dict__
                        place['city_id'] = place_city_id
                        place['location'] = {'type': 'Point', 'coordinates': [place['longitude'], place['latitude']]}
                        places_collection.insert_one(place)
                        print("Place `%s` was added to `%s`" % (place['name'], city['name']))
                        counter += 1
                city_collection.update_one({
                    '_id': city['_id']
                }, {
                    '$set': {
                        cursor_property: cursor
                    }
                })
                print('Found %d places of %d' % (counter, limit if limit is not None else -1))
                if cursor is False:
                    break

    @staticmethod
    def search_images_for_location(location_id: int, limit: int = 1000, batch_size: int = 50, cursor: int = None,
                                   min_id: int = None):
        search = InstagramLocationSearch(location_id)
        if search.get_location_info() is False:
            print('Location %d not found in Instagram' % int(location_id))
            return False, False
        search.next_cursor = cursor
        location_media_count = search.get_location_media_count()
        downloaded_media_count = 0
        current_images_count = 0
        print("Location %s (%s) have %d media items" % (
            search.get_location_name(), str(location_id), location_media_count))
        images = []
        while current_images_count < limit and downloaded_media_count < location_media_count:
            try:
                nodes = search.next_nodes(batch_size)
                if nodes is False:
                    break
                print("Download %d items" % len(nodes))
                downloaded_media_count += len(nodes)
                stop = False
                for node in nodes:
                    if node['is_video']:
                        continue
                    if min_id is not None and node['id'] <= min_id:
                        stop = True
                        break
                    images.append(node)
                    current_images_count += 1
                    if current_images_count >= limit:
                        break
                print("Found %d images of %d" % (current_images_count, limit))
                print("Next cursor = %s" % search.next_cursor)
                if stop is True:
                    break
            except (AttributeError, KeyError, ValueError, OSError) as er:
                print('Error!!!! ', er)
                break
            time.sleep(randint(3, 5))
        return images, search.next_cursor

    @staticmethod
    def search_images_for_place(place_id: int, limit: int = 1000, batch_size: int = 50, common_limit: bool = False,
                                only_new_posts: bool = False):
        images_collection = MongoDB.db()['images']
        place = MongoDB.db()['places'].find_one({'uid': place_id})
        if not place:
            raise NameError("Place not found")
        real_place_id = None
        if place:
            real_place_id = place['_id']
        max_id = None
        min_id = None
        if only_new_posts:
            try:
                if place:
                    max_id = images_collection.find({'place_id': place['_id']}).sort([('uid', -1)]).limit(1).next()
                    max_id = max_id['uid']
            except StopIteration:
                max_id = None
        else:
            try:
                if place:
                    min_id = images_collection.find({'place_id': place['_id']}).sort([('uid', 1)]).limit(1).next()
                    min_id = min_id['uid']
                    print('Place_id=%d continue from %d' % (int(place_id), int(min_id)))
            except StopIteration:
                min_id = None
        if common_limit is True:
            place_images_quantity = 0
            if place:
                place_images_quantity = images_collection.count({'place_id': place['_id']})
            limit = max(limit - place_images_quantity, 0)
        images, _ = DataLoader.search_images_for_location(place_id, limit, batch_size, cursor=min_id, min_id=max_id)
        if images is False:
            return False
        for image in images:
            if images_collection.count() == 0 or not images_collection.find_one({'uid': image['id']}):
                images_collection.insert_one({'place_id': real_place_id, 'uid': image['id'], 'shortcode': image[
                    'shortcode' if 'shortcode' in image else 'code'],
                                              'image_url': image[
                                                  'display_url' if 'display_url' in image else 'display_src'],
                                              'thumbnail_url': image['thumbnail_src'],
                                              'class': None, 'accuracy': None})

    @staticmethod
    def search_images_for_city(city_id: int, limit: int = 1000, batch_size: int = 50, common_limit: bool = False,
                               only_new_posts: bool = False):
        collection = MongoDB.db()['cities']
        place_collection = MongoDB.db()['places']
        query = {}
        if city_id is not None:
            query['city_id'] = city_id
        cities = []
        for city in collection.find(query):
            buffer_city = {'name': city['name'], '_id': city['_id'], 'places': []}
            for place in place_collection.find({'city_id': city['_id']}):
                buffer_city['places'].append(place['uid'])
            cities.append(buffer_city)

        for city in cities:
            print('City `%s` has %d places' % (city['name'], place_collection.count({'city_id': city['_id']})))
            for place_id in city['places']:
                DataLoader.search_images_for_place(place_id, limit, batch_size, common_limit=common_limit,
                                                   only_new_posts=only_new_posts)

    @staticmethod
    def download_predicted_images(dir, limit: int = None, batch_size=10, predicted_class='tpo', min_accuracy=None,
                                  max_accuracy=None,
                                  source='thumbnail_url'):
        if os.path.isdir(dir) is False:
            os.makedirs(dir)
        collection = MongoDB.db()['images']
        query = {'class': predicted_class, 'accuracy': {}}
        if min_accuracy is not None:
            query['accuracy']['$gte'] = min_accuracy
        if max_accuracy is not None:
            query['accuracy']['$lte'] = max_accuracy
        # if query['accuracy']:
        #     del query['accuracy']

        # dir_files = [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]
        counter = 0
        stop = False
        last_id = None
        # if len(dir_files) > 0:
        #     last_id = sorted(dir_files)[-1]
        # else:
        #     last_id = None
        total_count = collection.find(query).count()
        if limit is not None:
            total_count = limit
        while (limit is None or counter < limit) and collection.find(query).sort([('uid', 1)]).count() > 0:
            pool = multiprocessing.pool.ThreadPool()
            results = []
            if last_id is not None:
                query['uid'] = {'$gt': last_id}
            for image in collection.find(query).sort([('uid', 1)]).limit(batch_size):
                if limit is not None and counter >= limit:
                    break
                elif limit is None:
                    counter += 1
                if os.path.exists(os.path.join(dir, image['uid'] + '.jpg')) is False:
                    results.append(pool.apply_async(DataLoader.download_to_file,
                                                    (image[source], os.path.join(dir, image['uid'] + '.jpg'))))
                    if limit is not None:
                        counter += 1
                last_id = image['uid']
            for res in results:
                data = res.get()
            pool.close()
            pool.join()
            print('Downloaded %d of %d images' % (counter, total_count))

    @staticmethod
    def download_to_file(path, filename):
        data = requests.get(path).content
        f = open(filename, 'wb')
        f.write(data)
        f.close()
        return data
