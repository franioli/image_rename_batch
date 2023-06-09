"""Database for sensor-width.

This database if used when we construct camera intrinsics from exif data.

Authors: Ayush Baid
"""

import pandas as pd

from pathlib import Path


DEFAULT_SENSOR_DB_PATH = (
    Path(__file__).parent / "CameraSensorSizeDatabase/sensor_database.csv"
)


class SensorWidthDatabase:
    """Database class for sensor-width, reading data from a csv file."""

    def __init__(self, csv_path: str = DEFAULT_SENSOR_DB_PATH):
        """Initializes the database from a csv file"""

        self.df = pd.read_csv(csv_path)

        # convert string to lower-case
        self.df["CameraMaker"] = self.df["CameraMaker"].str.lower()
        self.df["CameraModel"] = self.df["CameraModel"].str.lower()

    def lookup(self, make: str, model: str) -> float:
        """Look-up the sensor width given the camera make and model.

        Args:
            make: make of the camera
            model: model of the camera

        Returns:
            sensor-width in mm
        """

        # preprocess query strings
        lower_make = make.split()[0].lower()
        lower_model = model.lower()

        selection_condition = (self.df["CameraMaker"] == lower_make) & (
            self.df["CameraModel"] == lower_model
        )
        selected = self.df.loc[selection_condition, "SensorWidth(mm)"]
        if len(selected) != 1:
            raise LookupError(
                f"make='{make}' and model='{model}' not found in sensor database"
            )

        return self.df.loc[selection_condition, "SensorWidth(mm)"].values[0]


if __name__ == "__main__":

    make = "NIKON CORPORATION"
    model = "NIKON D800"

    sensor_width_db = SensorWidthDatabase()
    sensor_width_mm = sensor_width_db.lookup(make, model)


    print("done")
