import multiprocessing.pool
import time
from io import BytesIO

import requests
from PIL import Image

from ImageClassifier import ImageClassifier
from MongoDB import MongoDB


class ImageRecognizer:
    __place_id__ = None
    __use_multithread__ = True
    __save_fields__ = {'class_field': 'class', 'accuracy_field': 'accuracy'}
    __classifier__ = None
    __collection__ = 'images'
    __source_field__ = 'image_url'
    __counter__ = 0
    __not_found_content_marker__ = 'content_not_found'
    __verbose__ = False

    def __init__(self, classifier: ImageClassifier, place_id: int = None, use_multithread: bool = True,
                 save_fields: dict = None, collection: str = 'images', source_field: str = 'image_url',
                 verbose: bool = False):
        self.__classifier__ = classifier
        self.__place_id__ = place_id
        self.__use_multithread__ = use_multithread
        if save_fields is not None:
            self.__save_fields__ = save_fields
        self.__collection__ = collection
        self.__source_field__ = source_field
        self.__verbose__ = verbose

        if 'class_field' not in self.__save_fields__:
            self.__save_fields__['class_field'] = 'class'
        if 'accuracy_field' not in self.__save_fields__:
            self.__save_fields__['accuracy_field'] = 'accuracy'

    def recognize_images_batch(self, limit: int = None, batch_size: int = 10):
        self.__counter__ = 0
        stop = False

        while stop is False:
            time_start = time.time()
            batch = self.__get_batch_images__(limit, batch_size)
            if len(batch) == 0:
                break

            load_time = time.time()
            loaded_images, batch = self.__download_images__(batch)
            load_time = time.time() - load_time

            time_predictions = time.clock()
            predictions = self.__classifier__.predict_batch(loaded_images)
            time_predictions = time.clock() - time_predictions

            for i, preds in enumerate(predictions):
                self.__save_prediction_result__(preds, batch[i])
                if self.__verbose__:
                    print(batch[i][self.__source_field__], " = ", preds)
            if self.__verbose__:
                print('Predict %d images of %d (time = %d, prediction_time = %d, load_time=%d)' % (
                    self.__counter__, limit, (time.time() - time_start), time_predictions, load_time))

    def __download_images__(self, images):
        collection = self.__get_collection__()
        loaded_images = [None] * len(images)
        if self.__use_multithread__:
            results = []
            pool = multiprocessing.pool.ThreadPool()
            for index, image in enumerate(images):
                results.append(pool.apply_async(self.__download_image__, (image[self.__source_field__], index)))
            for res in results:
                img, index = res.get()
                loaded_images[index] = img
            pool.close()
            pool.join()
        else:
            for i, image in enumerate(images):
                img, index = self.__download_image__(image[self.__source_field__], i)
                loaded_images[index] = img

        for i in reversed(range(len(loaded_images))):
            val = loaded_images[i]
            if val is None:
                collection.update_one({
                    '_id': images[i]['_id']
                }, {
                    "$set": {
                        self.__save_fields__['class_field']: self.__not_found_content_marker__,
                        self.__save_fields__['accuracy_field']: 0
                    }
                })
                del loaded_images[i]
                del images[i]
        return loaded_images, images

    def __get_batch_images__(self, limit: int = None, batch_size: int = 10) -> list:
        batch = []
        collection = self.__get_collection__()
        query = self.__prepare_query_params__()

        for image in collection.find(query).limit(batch_size):
            if limit is not None and self.__counter__ >= limit:
                break
            if self.__source_field__ not in image:
                continue
            batch.append(image)
            self.__counter__ += 1
        return batch

    def __save_prediction_result__(self, prediction, image_record):
        collection = self.__get_collection__()
        collection.update_one({
            '_id': image_record['_id']
        }, {
            "$set": self.__prepare_save_prediction_data__(prediction)
        })

    def __prepare_save_prediction_data__(self, prediction) -> dict:
        pred_class, pred_percent = prediction[0]
        return {
            self.__save_fields__['class_field']: pred_class,
            self.__save_fields__['accuracy_field']: float(pred_percent)
        }

    def __get_collection__(self):
        return MongoDB.db()[self.__collection__]

    def __prepare_query_params__(self) -> dict:
        query = {self.__save_fields__['class_field']: None}
        if self.__place_id__ is not None:
            query['place_id'] = self.__place_id__
        return query

    def __download_image__(self, path, index=None):
        try:
            response = requests.get(path)
            bytes = BytesIO(response.content)
            img = Image.open(bytes)
            img.verify()
            return BytesIO(response.content), index
        except:
            return None, index


class ImageRecognizerTypes(ImageRecognizer):
    __save_fields__ = {'class_field': 'types', 'accuracy_field': 'accuracy'}

    def __prepare_save_prediction_data__(self, prediction) -> dict:
        for i in range(len(prediction)):
            pred_class, pred_percent = prediction[i]
            pred_percent = float(pred_percent)
            prediction[i] = {'class': pred_class, 'accuracy': pred_percent}
        return {
            self.__save_fields__['class_field']: prediction,
        }

    def __prepare_query_params__(self) -> dict:
        query = super().__prepare_query_params__()
        query['class'] = 'tpo'
        return query
