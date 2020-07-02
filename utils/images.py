import requests
import os
import shutil
import random
from io import BytesIO

class ImageHandler():
    def __init__(self, pic_location, pictures_folder, start_index=-1):
        self.__REGEX_URL_PARSE = r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"""
        
        random.seed()
        
        self.__pic_location = pic_location
        self.__pictures_folder = pictures_folder
        self.__pics = self.__get_images_in_directory(self.__pictures_folder)
        self.__current_index = 0
        
        random.shuffle(self.__pics)
        
    ###########################################################################
    # Public facing methods
    ###########################################################################
    def parse_url_from_message(self, message):
        result = re.findall(self.__REGEX_URL_PARSE, message)
        
        url = None
        if len(result):
            found_urls = result[0]
            url = found_urls[0] if len(found_urls) > 0 else None
        return url
        
    def change_pic_from_url(self, image_url):
        response = requests.get(image_url)
        img_data = BytesIO(response.content)
        
        with open(self.__pic_location, "wb") as outfile:
            outfile.write(img_data.getbuffer())
            
    def get_current_pic(self):
        return self.__pics[self.__current_index]
            
    def next_pic(self):
        self.set_pic_from_index((self.__current_index + 1) % len(self.__pics))
        
    def set_pic_from_index(self, index):
        self.__current_index = index
        self.__copy_file_to_location('%s/%s' % (self.__pictures_folder, self.get_current_pic()), self.__pic_location)
            
    ###########################################################################
    # Private helper methods
    ###########################################################################
    def __get_images_in_directory(self, sub_path=''):
        return os.listdir(sub_path)
        
    def __copy_file_to_location(self, old_location, new_location):
        shutil.copy(old_location, new_location)