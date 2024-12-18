# -*- coding: utf-8 -*-
"""CLIPSeg_Generation.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1_c6pkiY2DdNXuqzd5slcgkPWtoFajOxm
"""

!pip install -q git+https://github.com/huggingface/transformers.git

import torch
import torch.nn as nn

print(torch.__version__)
print(nn.Module)

from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation

processor = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
model = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined")

import random, os, shutil
import numpy as np
from google.colab import drive

drive.mount('/content/drive')

BASE_PATH = '/content/drive/MyDrive/Spot_IL/Dataset_Ben/dataset_mixed'
TRAIN_PATH = os.path.join(BASE_PATH, 'train/')
TEST_PATH = os.path.join(BASE_PATH, 'test/')
GOAL_PATH = os.path.join(BASE_PATH, 'goal/')

import os
import torch
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation


OUTPUT_BASE_PATH = '/content/drive/MyDrive/Spot_IL/CLIPSeg_Mixed_Dataset_Train_Test'

OUTPUT_TRAIN_PATH = os.path.join(OUTPUT_BASE_PATH, 'train/')
OUTPUT_TEST_PATH = os.path.join(OUTPUT_BASE_PATH, 'test/')
OUTPUT_GOAL_PATH = os.path.join(OUTPUT_BASE_PATH, 'goal/')


os.makedirs(OUTPUT_TRAIN_PATH, exist_ok=True)
os.makedirs(OUTPUT_TEST_PATH, exist_ok=True)
os.makedirs(OUTPUT_GOAL_PATH, exist_ok=True)

PROMPT = ["red cube"]

def apply_clipseg_and_save(input_path, output_path, prompt):
    """
    Applying CLIPSeg segmentation on all images in the directory and save the results.
    """
    labels_path = os.path.join(input_path, 'labels.npy')
    if os.path.exists(labels_path):
        shutil.copy(labels_path, os.path.join(output_path, 'labels.npy'))
        print(f"Copied labels.npy to {output_path}")

    folders = os.listdir(input_path)
    folders = [f for f in os.listdir(input_path) if os.path.isdir(os.path.join(input_path, f))]
    for folder in folders:
        print(f'Working on folder : {folder}')
        folder_path = os.path.join(input_path, folder)
        output_folder_path = os.path.join(output_path, folder)
        os.makedirs(output_folder_path, exist_ok=True)

        images = sorted([f for f in os.listdir(folder_path) if f.endswith('.png')])
        for image_name in images:
            image_path = os.path.join(folder_path, image_name)
            image = Image.open(image_path)

            inputs = processor(text=prompt, images=[image] * len(prompt), return_tensors="pt")

            with torch.no_grad():
                outputs = model(**inputs)

            preds = outputs.logits.unsqueeze(1)
            segmented_image = torch.sigmoid(preds[0][0])

            output_image_path = os.path.join(output_folder_path, image_name)
            plt.imsave(output_image_path, segmented_image)


apply_clipseg_and_save(TRAIN_PATH, OUTPUT_TRAIN_PATH, PROMPT)
apply_clipseg_and_save(TEST_PATH, OUTPUT_TEST_PATH, PROMPT)
print(GOAL_PATH)
print(OUTPUT_GOAL_PATH)
apply_clipseg_and_save(GOAL_PATH, OUTPUT_GOAL_PATH, PROMPT)

print("Segmentation completed and saved!")