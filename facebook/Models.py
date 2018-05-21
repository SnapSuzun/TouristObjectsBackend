class City:
    city_id = None
    city_local_name = None
    latitude = None
    longitude = None
    name = None
    uid = None

    def __init__(self, **entries):
        self.__dict__.update(entries)

    def load(self, uid=None, city_id=None, name=None, city_local_name=None, latitude=None, longitude=None):
        self.uid = uid
        self.city_id = city_id
        self.name = name
        self.city_local_name = city_local_name
        self.latitude = latitude
        self.longitude = longitude

        return self

    @staticmethod
    def create(uid=None, city_id=None, name=None, city_local_name=None, latitude=None, longitude=None):
        city = City()
        return city.load(uid=uid, city_id=city_id, name=name, city_local_name=city_local_name, latitude=latitude,
                         longitude=longitude)


class Place:
    CATEGORY_CITY = 'City'

    uid = None
    latitude = None
    longitude = None
    category = None
    name = None

    def __init__(self, **entries):
        self.__dict__.update(entries)

    def is_city(self):
        return self.category == self.CATEGORY_CITY

    def load(self, uid, name=None, latitude=None, longitude=None, category=None):
        self.uid = uid
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.category = category
        return self

    @staticmethod
    def create(uid, name=None, latitude=None, longitude=None, category=None):
        place = Place()
        return place.load(uid, name=name, latitude=latitude, longitude=longitude, category=category)
