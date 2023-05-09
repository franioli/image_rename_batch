import logging
import multiprocessing
import shutil
import time
from functools import partial
from pathlib import Path
from typing import List, Tuple, TypedDict, Union

import cv2
import numpy as np
from tqdm import tqdm

from impreproc.images import Image, ImageList


class RenamingDict(TypedDict):
    old_name: str
    new_name: str
    date: str
    camera: str
    focal: str


def name_from_exif(
    fname: Union[str, Path],
    base_name: str = "IMG",
) -> Tuple[str, RenamingDict]:
    fname = Path(fname)
    img = Image(fname)
    exif = img.exif
    date_time = img._date_time
    if date_time is None:
        raise RuntimeError("Unable to get image date-time from exif.")
    try:
        camera_model = exif["Image Model"].printable
        camera_model = camera_model.replace(" ", "_")
    except:
        logging.warning("Unable to get camera model from exif.")
        camera_model = ""
    try:
        focal = exif["EXIF FocalLength"].printable
    except:
        logging.warning("Unable to get nominal focal length from exif.")
        focal = ""

    date_time_str = date_time.strftime("%Y%m%d_%H%M%S")
    new_name = f"{base_name}_{date_time_str}_{camera_model}{fname.suffix}"

    dic = RenamingDict(
        old_name=fname.name,
        new_name=new_name,
        date=date_time_str,
        camera=camera_model,
        focal=focal,
    )

    return new_name, dic


def overlay_text(
    image: np.ndarray,
    text: str,
    font_scale: int = 5,
    font_color: Tuple[int, int, int] = (255, 255, 255),
    font_thickness: int = 10,
    border_percentage: float = 0.03,
) -> np.ndarray:
    """Overlay text onto an image.

    Args:
        image (np.ndarray): The image onto which the text will be overlaid.
        text (str): The text to be overlaid onto the image.
        font_scale (int, optional): The size of the font for the text. Defaults to 5.
        font_color (Tuple[int, int, int], optional): The color of the text in BGR format. Defaults to (255, 255, 255).
        font_thickness (int, optional): The thickness of the text in pixels. Defaults to 10.
        border_percentage (float, optional): The percentage of the image border to use as a margin for the text. Defaults to 0.03.

    Returns:
        np.ndarray: The modified image with text overlaid.
    """

    h, w, _ = image.shape
    font = cv2.FONT_HERSHEY_SIMPLEX  # cv2.FONT_HERSHEY_DUPLEX
    bottomLeftCornerOfText = (int(w * border_percentage), int(h * border_percentage))
    fontScale = int(font_scale)
    fontColor = font_color
    thickness = int(font_thickness)
    text_border = int(font_thickness * 0.8)
    lineType = cv2.LINE_8
    # Text border
    cv2.putText(
        image,
        text,
        bottomLeftCornerOfText,
        font,
        fontScale,
        (0,),
        thickness + text_border,
        lineType,
    )
    # Inner text
    cv2.putText(
        image,
        text,
        bottomLeftCornerOfText,
        font,
        fontScale,
        fontColor,
        thickness,
        lineType,
    )

    return image


def copy_and_rename_fast(
    fname: Union[str, Path],
    dest_folder: Union[str, Path] = "renamed",
    base_name: str = "IMG",
    delete_original: bool = False,
) -> bool:
    """
    Renames an image file based on its exif data and copies it to a specified destination folder.

    Args:
        fname (Union[str, Path]): A string or Path object specifying the file path of the image to rename and copy.
        dest_folder (Union[str, Path], optional): A string or Path object specifying the destination directory path to copy the renamed image to. Defaults to "renamed".
        base_name (str, optional): A string to use as the base name for the renamed image file. Defaults to "IMG".
        delete_original (bool, optional): Whether to delete the original image file after copying the renamed image. Defaults to False.

    Returns:
        bool: Returns True if the image was successfully renamed and copied to the destination folder.

    Raises:
        RuntimeError: If the exif data cannot be read or if the image date-time cannot be retrieved from the exif data.
    """
    fname = Path(fname)
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(exist_ok=True, parents=True)

    new_name, _ = name_from_exif(fname=fname, base_name=base_name)

    # Do actual copy
    dst = dest_folder / new_name
    shutil.copyfile(src=fname, dst=dst)

    # If delete_original is set to True, delete original image
    if delete_original:
        fname.unlink()

    return True


def copy_and_rename_overlay(
    fname: Union[str, Path],
    dest_folder: Union[str, Path] = "renamed",
    base_name: str = "IMG",
    overlay_name: bool = False,
    delete_original: bool = False,
) -> dict:
    """
    Copies an image and renames it according to its EXIF data. Can also overlay the new name on the copied image and
    optionally delete the original image.

    Args:
        fname (Union[str, Path]): The file path of the image to be copied and renamed.
        dest_folder (Union[str, Path], optional): The destination folder where the copied image will be saved. Defaults
        to "renamed".
        base_name (str, optional): The base name to be used for the copied image. Defaults to "IMG".
        overlay_name (bool, optional): Whether or not to overlay the new name on the copied image. Defaults to False.
        delete_original (bool, optional): Whether or not to delete the original image after copying and renaming. Defaults
        to False.

    Returns:
        dict: A dictionary containing the extracted EXIF data.

    Raises:
        TypeError: If fname or dest_folder is not a string or a Path object.
    """
    # Read image
    image = cv2.imread(str(fname))

    # Get new name
    new_name, dic = name_from_exif(fname=fname, base_name=base_name)

    # Overlay name on image
    if overlay_name:
        image = overlay_text(image=image, text=new_name)

    # Write image
    cv2.imwrite(str(dest_folder / new_name), image)

    # If delete_original is set to True, delete original image
    if delete_original:
        fname.unlink()

    return dic


class ImageRenamer:
    """
    A class for renaming a list of images.

    Args:
        image_list (ImageList): A list of images to be renamed.
        dest_folder (Union[str, Path], optional): The destination folder where the renamed images will be saved. Defaults to "renamed".
        base_name (str, optional): The base name for the renamed images. Defaults to "IMG".
        overlay_name (bool, optional): Whether to overlay the new name on the image. Defaults to False.
        delete_original (bool, optional): Whether to delete the original image after renaming. Defaults to False.
        parallel (bool, optional): Whether to use multiprocessing for faster renaming. Defaults to False.

    Attributes:
        renaming_dict (dict): A dictionary of the old and new names, if build_dictionary is set to True.

    Methods:
        rename_fast(self) -> bool:
            Renames the images without overlaying the new name.

            Returns:
                bool: True if all images were renamed successfully, False otherwise.

        rename(self) -> dict:
            Renames the images and overlays the new name if overlay_name is set to True. Returns a dictionary of the old and new names.

            Returns:
                dict: A dictionary of the old and new names.
    """

    def __init__(
        self,
        image_list: ImageList,
        dest_folder: Union[str, Path] = "renamed",
        base_name: str = "IMG",
        overlay_name: bool = False,
        delete_original: bool = False,
        parallel: bool = False,
    ) -> None:
        """Initializes the ImageRenamer class.

        Args:
            image_list (ImageList): A list of paths to the images to be renamed.
            dest_folder (Union[str, Path], optional): The destination folder for the renamed images. Defaults to "renamed".
            base_name (str, optional): The base name for the renamed images. Defaults to "IMG".
            overlay_name (bool, optional): Whether to overlay the new name on the image. Defaults to False.
            build_dictionary (bool, optional): Whether to build a dictionary mapping old names to new names. Defaults to False.
            delete_original (bool, optional): Whether to delete the original images after renaming. Defaults to False.
            parallel (bool, optional): Whether to use multiprocessing. Defaults to False.
        """
        self.image_list = image_list
        self.dest_folder = Path(dest_folder)
        self.base_name = base_name
        self.delete_original = delete_original
        self.overlay_name = overlay_name
        self.parallel = parallel

        self.renaming_dict = {}

        if self.dest_folder.exists():
            logging.warning(
                f"Destination folder {self.dest_folder} already exists. Existing files may be overwritten."
            )
        else:
            self.dest_folder.mkdir(parents=True)

    def rename_fast(self) -> bool:
        """Rename the images using multiprocessing and without overlaying the image names.

        Returns:
            bool: True if all files were renamed successfully.
        Raises:
            RuntimeError: If unable to rename a file.
        """
        func = partial(
            copy_and_rename_fast,
            dest_folder=self.dest_folder,
            base_name=self.base_name,
            delete_original=self.delete_original,
        )
        if self.parallel:
            with multiprocessing.Pool() as p:
                list(tqdm(p.imap(func, self.image_list)))

        else:
            for file in tqdm(self.image_list):
                if not func(file):
                    raise RuntimeError(f"Unable to rename file {file.name}")
        return True

    def rename(self) -> dict:
        """
        Rename the images in `self.image_list`, applying the `copy_and_rename_overlay` function with the specified parameters
        to each image. Return a dictionary mapping the original index of each image in `self.image_list` to its new name
        generated by `copy_and_rename_overlay`.

        Returns:
            A dictionary mapping integers to strings, where each integer is an index in `self.image_list` and the corresponding
            string is the new name of the image at that index after being renamed by `copy_and_rename_overlay`.

        Raises:
            RuntimeError: If an error occurs while renaming an image.

        """
        func = partial(
            copy_and_rename_overlay,
            dest_folder=self.dest_folder,
            base_name=self.base_name,
            overlay_name=self.overlay_name,
        )
        if self.parallel:
            with multiprocessing.Pool() as p:
                out = list(tqdm(p.imap(func, self.image_list)))
            self.renaming_dict = {k: v for k, v in enumerate(out)}

        else:
            for i, file in enumerate(tqdm(self.image_list)):
                self.renaming_dict[i] = func(file)

        return self.renaming_dict
