import json
import os
import random
import time
from PIL import Image
import gc


class MrBeastify:
    def __init__(self, images_path="images/"):
        self.images_path = images_path
        self.use_alternative_images = False
        self.flip_blacklist = []
        self.last_indexes = [-1] * 8
        self.resources = []
        self.highest_image_index = self._get_highest_image_index()

    def release_resources(self):
        # close or release any resources, if needed
        for resource in self.resources:
            resource.close()  # or any appropriate method

    def apply_overlay(self, thumbnail_path, overlay_image_path, flip=False):
        # Open thumbnail and overlay image using PIL inside a with block
        with Image.open(thumbnail_path) as thumbnail:
            with Image.open(overlay_image_path) as overlay:
                thumbnail = thumbnail.resize((1280, 720))

                if flip:
                    overlay = overlay.transpose(Image.FLIP_LEFT_RIGHT)

                # Overlay images
                thumbnail.paste(overlay, (0, 0), overlay)

                # Convert the image mode to RGB before saving if it's not already
                if thumbnail.mode != "RGB":
                    thumbnail = thumbnail.convert("RGB")

                # Save the overlayed image with the original thumbnail's filename
                thumbnail.save(thumbnail_path)

    def _get_image_path(self, index):
        return os.path.join(self.images_path, f"{index}.png")

    def get_random_image_from_directory(self):
        random_index = -1
        while random_index in self.last_indexes or random_index < 0:
            random_index = random.randint(1, self.highest_image_index)
        self.last_indexes.pop(0)
        self.last_indexes.append(random_index)
        return self._get_image_path(random_index)

    def _check_image_existence(self, index):
        return os.path.exists(self._get_image_path(index))

    def _get_highest_image_index(self):
        i = 1
        while self._check_image_existence(i):
            i += 1
        return i - 1

    def get_flip_blacklist(self, blacklist_path="./images/flip_blacklist.json"):
        # In this translation, a local file will be used for the blacklist
        try:
            with open(blacklist_path, "r") as file:
                data = json.load(file)
                self.use_alternative_images = data.get("useAlternativeImages", False)
                self.flip_blacklist = data.get("blacklistedImages", [])
        except:
            print("No flip blacklist found. Proceeding without it.")

    def apply_to_thumbnails(self, thumbnail_path):
        # This function just overlays one image for simplicity
        overlay_image_index = self.get_random_image_from_directory()
        flip = random.random() < 0.25
        if flip and overlay_image_index in self.flip_blacklist:
            flip = False
        self.apply_overlay(thumbnail_path, overlay_image_index, flip)

    def delete_file(self, thumbnail_path, max_retries=5, delay_between_retries=2):
        os.remove(thumbnail_path)


# Usage
# mrbeastify = MrBeastify()
# mrbeastify.get_flip_blacklist()
# mrbeastify.apply_to_thumbnails("path_to_thumbnail_image.png")
