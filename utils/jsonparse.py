import json

# I took this from a blog post:
# https://www.haykranen.nl/2016/02/13/handling-complex-nested-dicts-in-python/
class JsonParse():
    def __init__(self, json_data):
        self.__data = json_data

    def get(self, path, default = None):
        keys = path.split("/")
        val = None

        for key in keys:
            if val:
                if isinstance(val, list):
                    val = [ v.get(key, default) if v else None for v in val]
                else:
                    val = val.get(key, default)
            else:
                val = self.__data.get(key, default)

            if not val:
                break;

        return val