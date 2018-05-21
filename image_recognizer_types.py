from ImageRecognizer import ImageRecognizerTypes
from ImageClassifier import ImageClassifier
import argparse
import os
import time


def parse_arguments():
    parser = argparse.ArgumentParser()  # Input Arguments
    parser.add_argument(
        '--model-file',
        help='path to model file',
        required=True,
        default='jobs'
    )
    parser.add_argument(
        '--classes',
        help='path to file with classes map',
        required=True,
    )
    parser.add_argument(
        '--info',
        help='path to file with common info',
        required=True,
    )
    args = parser.parse_args()
    arguments = args.__dict__
    if not os.path.isfile(arguments['classes']):
        print("Can't load file with classes - '" + arguments['classes'] + "'")
        exit()

    if not os.path.isfile(arguments['info']):
        print("Can't load file with info - '" + arguments['info'] + "'")
        exit()
    return arguments


arguments = parse_arguments()
classifier = ImageClassifier(arguments['model_file'], arguments['classes'], arguments['info'])

start = time.time()
recognizer = ImageRecognizerTypes(classifier, save_fields={'class_field': 'classes'},
                                  verbose=True)
recognizer.recognize_images_batch(limit=10000, batch_size=10)
# recognize_images(recognizer, 1000)
# recognize_images_batch(classifier, limit=10000, batch_size=10,
#                       result_fields={'class_field': 'class1', 'accuracy_field': 'accuracy1'})
# recognize_images_batch(recognizer, limit=10000, batch_size=10, place_id=294100933965764)
# recognize_images_batch(recognizer, limit=10000, batch_size=10, place_id=422387764530637)
# recognize_images_batch(recognizer, limit=10000, batch_size=10, place_id=163218223742220)
# recognize_images_batch(recognizer, limit=10000, batch_size=10, place_id=476084812572097)
# recognize_images_batch(recognizer, limit=10000, batch_size=10, place_id=199514816836803)
# recognize_images_batch(recognizer, limit=10000, batch_size=10, place_id=142932632416588)
print("Total time = %d" % (time.time() - start))
