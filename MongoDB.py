from pymongo import MongoClient
import os.path
import configparser


class MongoDB:
    __CONFIGURATION_FILENAME__ = 'db.ini'
    __CONFIGURATION_SECTION__ = 'MongoDB'

    __instance = None
    __connection = None

    __host__ = None
    __port__ = None

    def __init__(self):
        self.__load_config__()
        self.__connection = MongoClient(self.__host__, int(self.__port__))

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

    def __load_config__(self):
        path = os.path.join(os.path.dirname(__file__), self.__CONFIGURATION_FILENAME__)
        if not os.path.isfile(path):
            raise FileNotFoundError("Configuration file '{0}' not found.".format(path))
        config = configparser.ConfigParser()
        config.read(path)
        if self.__CONFIGURATION_SECTION__ not in config:
            raise KeyError("Section '{0}' not found in configuration file.".format(self.__CONFIGURATION_SECTION__))
        if 'host' not in config[self.__CONFIGURATION_SECTION__]:
            raise KeyError("Property 'AppId' not found in section '{0}'".format(self.__CONFIGURATION_SECTION__))
        if 'port' not in config[self.__CONFIGURATION_SECTION__]:
            raise KeyError("Property 'AppSecret' not found in section '{0}'".format(self.__CONFIGURATION_SECTION__))
        self.__host__ = config[self.__CONFIGURATION_SECTION__]['host']
        self.__port__ = config[self.__CONFIGURATION_SECTION__]['port']
