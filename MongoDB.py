from pymongo import MongoClient


class MongoDB:
    __instance = None
    __connection = None

    def __init__(self):
        self.__connection = MongoClient('mongodb://tourist_objects:jnrhsnrf995@localhost/tourist_objects', 27017)

    @staticmethod
    def inst():
        if MongoDB.__instance is None:
            MongoDB.__instance = MongoDB()
        return MongoDB.__instance

    @staticmethod
    def db(database_name: str = 'tourist_objects'):
        return MongoDB.connection()[database_name]

    @staticmethod
    def connection() -> MongoClient:
        return MongoDB.inst().__connection
