import json

import numpy as np
from keras.models import load_model
from keras.preprocessing import image
from tensorflow.python.lib.io import file_io
import multiprocessing.pool
from keras import backend as K


class ImageClassifier:
    __model = None
    __path_to_model = None
    __classes = None
    __inverted_classes = None
    __model_info = None
    __image_target_size = None
    __save_dir = None

    def __init__(self, path_to_model, path_to_file_with_classes, path_to_info_file, image_target_size=None,
                 save_dir=None, data_format='channels_last', color_mode='rgb'):
        self.__classes = json.loads(file_io.read_file_to_string(path_to_file_with_classes))
        self.__inverted_classes = dict(zip(self.__classes.values(), self.__classes.keys()))
        self.__model_info = json.loads(file_io.read_file_to_string(path_to_info_file))
        self.__path_to_model = path_to_model
        self.__model = load_model(path_to_model)
        self.__image_target_size = image_target_size
        self.__save_dir = save_dir
        self.__data_format = data_format
        self.__color_mode = color_mode
        if not image_target_size:
            self.__image_target_size = (int(self.__model_info['img_width']), int(self.__model_info['img_height']))

        if self.__color_mode == 'rgb':
            if self.__data_format == 'channels_last':
                self.image_shape = self.__image_target_size + (3,)
            else:
                self.image_shape = (3,) + self.__image_target_size
        else:
            if self.__data_format == 'channels_last':
                self.image_shape = self.__image_target_size + (1,)
            else:
                self.image_shape = (1,) + self.__image_target_size

    def predict(self, path):
        img, _ = self.__load_and_prepare_image(path)
        preds = self.__model.predict(img)
        return self.__decode_predictions(preds)[0]

    def predict_batch(self, paths):
        batch_x = np.zeros((len(paths),) + self.image_shape, dtype=K.floatx())
        batch_x_success = np.ones(len(paths), dtype=bool)

        results = []
        pool = multiprocessing.pool.ThreadPool()
        for index, path in enumerate(paths):
            results.append(pool.apply_async(self.__load_and_prepare_image, (path, index)))
        for res in results:
            img, index = res.get()
            if img is None:
                batch_x_success[index] = False
            else:
                batch_x[index] = img
        pool.close()
        pool.join()

        return self.__decode_predictions(self.__model.predict_on_batch(batch_x))

    def __load_and_prepare_image(self, path, index=None):
        if path is None:
            print(index)
        img = image.load_img(path, target_size=self.__image_target_size)
        x = image.img_to_array(img)
        x = np.expand_dims(x, axis=0)
        return x, index

    def __decode_predictions(self, preds, top=5):
        """Decodes the prediction of an ImageNet model.

        # Arguments
            preds: Numpy tensor encoding a batch of predictions.
            top: integer, how many top-guesses to return.

        # Returns
            A list of lists of top class prediction tuples
            `(class_name, class_description, score)`.
            One list of tuples per sample in batch input.

        # Raises
            ValueError: in case of invalid shape of the `pred` array
                (must be 2D).
        """

        results = []
        for pred in preds:
            top_indices = pred.argsort()[-top:][::-1]
            result = [(self.__inverted_classes[i], pred[i],) for i in top_indices]
            result.sort(key=lambda x: x[1], reverse=True)
            results.append(result)
        return results
