import streamlit as st

import pandas as pd
import numpy as np

from google.cloud import firestore_v1

from queue import Queue

from datetime import datetime

import altair as alt

import random

DEVICE_DISPLAY_MAX = 4
MINUTES_TO_DISPLAY = 45
COLUMN_COUNT = 2

FRIENDLY_DEVICE_NAMES = {
  "dev:860322068099875": "Wall Screen",
  "dev:860322067840667": "True Fridge",
  "dev:860322068093811": "Blues Billboard",
  "dev:860322068094264": "Booth",
}

TITLE = "Blue/Useful Sensors Retail Analytics"

db = firestore_v1.Client()
collection_ref = db.collection(u'person-sensor-blues-data')

q = Queue()


def on_snapshot(collection_snapshot, changes, read_time):
    docs_by_device = {}
    for doc in collection_snapshot:
        doc_dict = doc.to_dict()
        if "device" not in doc_dict or "time" not in doc_dict or "num_faces" not in doc_dict:
            continue
        device = doc_dict["device"]
        if device not in docs_by_device:
            docs_by_device[device] = []
        docs_by_device[device].append(doc_dict)

    for device in docs_by_device.keys():
        docs_by_device[device].sort(key=lambda x: x["time"], reverse = True)
        most_recent_time = docs_by_device[device][0]["time"]
        cutoff_time = most_recent_time - (MINUTES_TO_DISPLAY * 60)
        most_recent = []
        for doc in docs_by_device[device]:
            if doc["time"] > cutoff_time:
                most_recent.append(doc)
        docs_by_device[device] = most_recent

    frames_by_device = {}    
    for device in docs_by_device.keys():
        doc_dicts = docs_by_device[device]
        friendly_times = []
        for doc_dict in doc_dicts:
            json_time = doc_dict["time"] * 1000
            num_faces = doc_dict["num_faces"]
            if "num_facing_faces" in doc_dict:
                num_facing_faces = doc_dict["num_facing_faces"]
            else:
                num_facing_faces = 0
            friendly_times.append({
                "time": json_time,
                "People": num_faces,
                "Attention": num_facing_faces
            })
        frames_by_device[device] = pd.DataFrame(friendly_times, columns=["time", "People", "Attention"])

    q.put(frames_by_device)    # Put data into the Queue

collection_watch = collection_ref.on_snapshot(on_snapshot)

st.set_page_config(layout="wide")
st.title("Blues/Useful Sensors Person Counting Demo")
columns = st.columns(COLUMN_COUNT)

snaps = []
for i in range(DEVICE_DISPLAY_MAX):
    with columns[i % COLUMN_COUNT]:
        snaps.append(st.empty())

while True:
    frames_by_device = q.get()    # Read from the Queue
    for index, device in enumerate(frames_by_device.keys()):
        if index >= DEVICE_DISPLAY_MAX:
            break
        frame = frames_by_device[device]
        if device in FRIENDLY_DEVICE_NAMES:
            friendly_device_name = FRIENDLY_DEVICE_NAMES[device]
        else:
            friendly_device_name = device
        latest_value = int(round(frame["People"].values[0]))
        title = f"{friendly_device_name} - {latest_value} People"
        chart = alt.Chart(frame, title=title).mark_area(
          line={'color':'darkgreen'},
          color=alt.Gradient(
              gradient='linear',
              stops=[alt.GradientStop(color='white', offset=0),
                     alt.GradientStop(color='darkgreen', offset=1)],
              x1=1,
              x2=1,
              y1=1,
              y2=0
          )
        ).encode(
            alt.X('time:T', axis=alt.Axis(
                title="Time"
            )),
            alt.Y(alt.repeat('layer'),
                type='quantitative',
                axis=alt.Axis(
                    title="People",
                )
            ).scale(domain=(0,5)),
            color=alt.ColorDatum(alt.repeat('layer'))
        ).repeat(layer=["People", "Attention"])
        snaps[index].altair_chart(chart, use_container_width=True)
