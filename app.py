import streamlit as st

import pandas as pd
import numpy as np

from google.cloud import firestore_v1

from queue import Queue

from datetime import datetime

DEVICE_DISPLAY_MAX = 4

db = firestore_v1.Client()
collection_ref = db.collection(u'person-sensor-blues-data')

q = Queue()


def on_snapshot(collection_snapshot, changes, read_time):
  docs_by_device = {}
  for doc in collection_snapshot:
    doc_dict = doc.to_dict()
    if "device" not in doc_dict or "time" not in doc_dict or "num_faces" not in doc_dict:
      continue
    device =  doc_dict["device"]
    if device not in docs_by_device:
      docs_by_device[device] = []
    docs_by_device[device].append(doc_dict)

  for device in docs_by_device.keys():
    docs_by_device[device].sort(key=lambda x: x["time"], reverse = True)
    most_recent_time = docs_by_device[device][0]["time"]
    cutoff_time = most_recent_time - (15 * 60)
    most_recent = []
    for doc in docs_by_device[device]:
      if doc["time"] < cutoff_time:
        most_recent.append(doc)
    docs_by_device[device] = most_recent

  frames_by_device = {}  
  for device in docs_by_device.keys():
    doc_dicts = docs_by_device[device]
    friendly_times = []
    for doc_dict in doc_dicts:
      dt = datetime.fromtimestamp(doc_dict["time"])
      friendly_time = dt.strftime("%X")
      friendly_times.append({
        "time": friendly_time,
        "num_faces": doc_dict["num_faces"]
      })
    frames_by_device[device] = pd.DataFrame(friendly_times, columns=["time", "num_faces"])

  q.put(frames_by_device)  # Put data into the Queue

collection_watch = collection_ref.on_snapshot(on_snapshot)

# below will run in main thread
snaps = []
for i in range(DEVICE_DISPLAY_MAX):
  snaps.append(st.empty())

while True:
  # q.get() is a blocking function. thus recommend to add timeout
  frames_by_device = q.get()  # Read from the Queue
  for index, device in enumerate(frames_by_device.keys()):
    if index >= DEVICE_DISPLAY_MAX:
      break
    frame = frames_by_device[device]
    snaps[index].line_chart(data=frame, x="time", y="num_faces")
