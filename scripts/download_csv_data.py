"""A simple script for downloading the data specific to the Multicare Project."""
# standard
from collections import namedtuple
import time
from pathlib import Path
# external
import requests
# internal
from sensorthings_utils.frost_data_retrieval import (
        fetch_observations,
        observations_link_from_thing,
        CuratedDataSet
        )

MULTICARE_FROST_URL = "https://multicare.bk.tudelft.nl/FROST-Server/v1.1/"

if __name__ == "__main__":
    params = {"$filter":"@iot.id gt 3"}
    things = requests.get(
            (f"{MULTICARE_FROST_URL}" + "Things"),
            params
            ).json()

    multicare_metadata = namedtuple(
            "metadata",
            ["apartment_name", "country", "floor", "orientation", "room_type"]
            )

    now = int(time.time())

    for t in things["value"]:
        properties = t["properties"]
        # Multicare Specific Metadata    
        apartment_name = t["name"]
        country = "Romania" if "Bucharest" in apartment_name else "Italy"
        floor = properties["floor"]
        orientation = properties["orientation"]
        room_type = properties["room_type"]
        

        datastream_link = t["Datastreams@iot.navigationLink"]
        datastreams = requests.get(datastream_link).json()
        for ds in datastreams["value"]:
            md = multicare_metadata(
                    apartment_name, country, floor, orientation, room_type
                    )

            curated_dataset = CuratedDataSet(md, [])
            observation_link = observations_link_from_thing(
                    MULTICARE_FROST_URL,
                    t["name"],
                    ds["name"]
                    )
            curated_dataset.extend_observations(
                    fetch_observations(observation_link)
                    )
            save_path = Path(f"{apartment_name}-{ds["name"]}-{now}.csv")
            curated_dataset.to_csv(path=save_path)
            print(f"Saved to {save_path}.")


