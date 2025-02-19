# -*- coding: utf-8 -*-
"""DINO_Encoder_Overfit.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1frbCLBtIOznurNfZV8Rh4Uc-SniXpegv
"""

from google.colab import drive
drive.mount('/content/drive', force_remount=True)

# Commented out IPython magic to ensure Python compatibility.
!git clone https://github.com/IDEA-Research/GroundingDINO.git
# %cd GroundingDINO
!pip install -e .

!mkdir weights
!wget -O weights/groundingdino_swint_ogc.pth https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

import os
import torch
from torch.utils.data import Dataset
from PIL import Image
import numpy as np
from google.colab import drive

class SPOTDataLoader(Dataset):
    def __init__(self, root_dir, labels_file, transform=None):
        print("Initializing SPOTDataLoader...")
        self.root_dir = root_dir
        self.transform = transform
        self.labels = np.load(labels_file)
        # print(f"Loaded labels from {labels_file} with shape: {self.labels.shape}")

        if torch.cuda.is_available():
            self.cuda = True
            # print("CUDA is available. Using GPU.")
        else:
            self.cuda = False
            # print("CUDA is not available. Using CPU.")

    def __len__(self):
        length = self.labels.shape[0]
        # print(f"Dataset length: {length}")
        return length

    def __getitem__(self, idx):
        # print(f"\nFetching data for index: {idx}")
        folder_name = format(idx, '05d')
        folder_path = os.path.join(self.root_dir, folder_name)
        # print(f"Constructed folder path: {folder_path}")

        input_images = []
        for i in range(4):
            input_image_path = os.path.join(folder_path, f"{i}.jpg")
            # print(f"Loading input image {i} from: {input_image_path}")
            image = Image.open(input_image_path).convert('RGB')
            # print(f"Loaded input image {i} with size: {image.size}")
            if self.transform:
                image = self.transform(image)
                #print(f"Applied transform to input image {i}.")
            input_images.append(image)

        goal_images = []
        for i in range(1):
            goal_image_path = os.path.join(folder_path, f"goal_{i}.jpg")
            # print(f"Loading goal image {i} from: {goal_image_path}")
            image = Image.open(goal_image_path).convert('RGB')
            # print(f"Loaded goal image {i} with size: {image.size}")
            if self.transform:
                image = self.transform(image)
                # print(f"Applied transform to goal image {i}.")
            goal_images.append(image)

        label = self.labels[idx]
        # print(f"Label for index {idx}: {label}")

        if self.cuda:
            input_images_tensor = torch.stack(input_images, dim=0).cuda()
            goal_images_tensor = torch.stack(goal_images, dim=0).cuda()
            label_tensor = torch.tensor(label).cuda()
            # print("Moved input images, goal images, and label tensor to GPU.")
        else:
            input_images_tensor = torch.stack(input_images, dim=0)
            goal_images_tensor = torch.stack(goal_images, dim=0)
            label_tensor = torch.tensor(label)
            # print("Using CPU tensors for input images, goal images, and label tensor.")

        # print(f"Input images tensor shape: {input_images_tensor.shape}")
        # print(f"Goal images tensor shape: {goal_images_tensor.shape}")
        # print(f"Label tensor: {label_tensor}")

        return input_images_tensor, goal_images_tensor, label_tensor

import torch
import torch.nn as nn
import torch.nn.functional as F
from groundingdino.util.slconfig import SLConfig
from groundingdino.models import build_model

class CrossAttentionBlock(nn.Module):
    def __init__(self, embed_dim, num_heads=8):
        super(CrossAttentionBlock, self).__init__()
        self.mha = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)

    def forward(self, query, key_value):
        # print(f"[CrossAttentionBlock] Query shape: {query.shape}, Key/Value shape: {key_value.shape}")
        attn, _ = self.mha(query, key_value, key_value)
        # print(f"[CrossAttentionBlock] Attention output shape: {attn.shape}")
        return attn


class GroundingDinoFeatureExtractor(nn.Module):
    def __init__(self, base_model, device='cuda'):
        super(GroundingDinoFeatureExtractor, self).__init__()
        self.model = base_model
        self.device = device
        self._features = None
        # print("Hooking into transformer.encoder.layers[-1] to use enhanced encoder features.")
        self.hook_handle = self.model.transformer.encoder.layers[-1].register_forward_hook(self.hook_fn)

    def hook_fn(self, module, input, output):
        # print("[Hook] Module:", module)
        # print("[Hook] Input shapes:", [inp.shape for inp in input])
        '''
        if isinstance(output, (list, tuple)):
            print("[Hook] Output shapes:", [o.shape for o in output])
        else:
            print("[Hook] Output shape:", output.shape)
        '''
        self._features = output

    def forward(self, images, text_prompts):
        # print(f"[FeatureExtractor] Received images with shape: {images.shape}")
        # print(f"[FeatureExtractor] Received text_prompts: {text_prompts}")
        images = images.to(self.device)

        # Passing prompts as 'captions=' so GroundingDINO doesn't treat them as bounding-box targets
        _ = self.model(images, captions=text_prompts)
        '''
        if self._features is not None:
            print(f"[FeatureExtractor] Extracted features shape: {self._features.shape}")
        else:
            print("[FeatureExtractor] Warning: No features extracted!")
        '''
        return self._features

class DINOCrossAttentionMLP(nn.Module):
    def __init__(self, config_file, weight_file, num_cameras=4, embed_dim=256, device='cuda'):
        super(DINOCrossAttentionMLP, self).__init__()
        self.device = device
        self.num_cameras = num_cameras

        cfg = SLConfig.fromfile(config_file)
        base_model = build_model(cfg)
        checkpoint = torch.load(weight_file, map_location=device)
        state_dict = checkpoint['model'] if 'model' in checkpoint else checkpoint
        state_dict = {
            (k[len("module."): ] if k.startswith("module.") else k): v
            for k, v in state_dict.items()
        }
        base_model.load_state_dict(state_dict, strict=False)
        base_model.to(device)
        base_model.train()

        self.feature_extractor = GroundingDinoFeatureExtractor(base_model, device=device)
        self.cross_attention = CrossAttentionBlock(embed_dim, num_heads=8)

        self.fc_layer1 = nn.Sequential(
            nn.Linear(2 * embed_dim * num_cameras, 1024),
            nn.ReLU()
        )
        self.fc_layer2 = nn.Sequential(
            nn.Linear(1024, 1024),
            nn.ReLU()
        )
        self.fc_layer3 = nn.Sequential(
            nn.Linear(1024, 1024),
            nn.ReLU()
        )
        self.fc_layer4 = nn.Sequential(
            nn.Linear(1024, 1024),
            nn.ReLU()
        )
        self.fc_layer5 = nn.Linear(1024, 3)

        self.to(device)

    def forward(self, current_images, goal_images, text_prompts):
        # print(f"[DINOCrossAttentionMLP] current_images shape: {current_images.shape}")
        # print(f"[DINOCrossAttentionMLP] goal_images shape: {goal_images.shape}")
        # print(f"[DINOCrossAttentionMLP] text_prompts: {text_prompts}")

        if goal_images.size(1) == 1 and self.num_cameras > 1:
            goal_images = goal_images.expand(-1, self.num_cameras, -1, -1, -1)
            # print("[DINOCrossAttentionMLP] Repeated goal_images to match num_cameras.")
            # print(f"[DINOCrossAttentionMLP] New goal_images shape: {goal_images.shape}")

        current_features_list = []
        goal_features_list = []

        for cam in range(self.num_cameras):
            # print(f"[Camera {cam}] Processing images...")
            curr_img = current_images[:, cam, :, :, :]
            goal_img = goal_images[:, cam, :, :, :]
            # print(f"[Camera {cam}] curr_img shape: {curr_img.shape}, goal_img shape: {goal_img.shape}")

            curr_feat = self.feature_extractor(curr_img, text_prompts)
            goal_feat = self.feature_extractor(goal_img, text_prompts)

            if curr_feat is None or goal_feat is None:
                print(f"[Camera {cam}] Warning: Feature extraction returned None!")
                continue

            # print(f"[Camera {cam}] curr_feat shape: {curr_feat.shape}, goal_feat shape: {goal_feat.shape}")

            curr_attn = curr_feat + self.cross_attention(curr_feat, goal_feat)
            goal_attn = goal_feat + self.cross_attention(goal_feat, curr_feat)
            # print(f"[Camera {cam}] curr_attn shape: {curr_attn.shape}, goal_attn shape: {goal_attn.shape}")

            curr_pool = curr_attn.mean(dim=1)
            goal_pool = goal_attn.mean(dim=1)
            # print(f"[Camera {cam}] curr_pool shape: {curr_pool.shape}, goal_pool shape: {goal_pool.shape}")

            current_features_list.append(curr_pool)
            goal_features_list.append(goal_pool)

        # print(f"[DINOCrossAttentionMLP] Number of camera features (current): {len(current_features_list)}")
        # print(f"[DINOCrossAttentionMLP] Number of camera features (goal): {len(goal_features_list)}")

        current_features = torch.cat(current_features_list, dim=1)
        goal_features = torch.cat(goal_features_list, dim=1)
        # print(f"[DINOCrossAttentionMLP] Concatenated current_features shape: {current_features.shape}")
        # print(f"[DINOCrossAttentionMLP] Concatenated goal_features shape: {goal_features.shape}")

        features = torch.cat([current_features, goal_features], dim=1)
        # print(f"[DINOCrossAttentionMLP] Combined features shape: {features.shape}")

        x = self.fc_layer1(features)
        # print(f"[DINOCrossAttentionMLP] After fc_layer1: {x.shape}")
        x = self.fc_layer2(x)
        # print(f"[DINOCrossAttentionMLP] After fc_layer2: {x.shape}")
        x = self.fc_layer3(x)
        # print(f"[DINOCrossAttentionMLP] After fc_layer3: {x.shape}")
        x = self.fc_layer4(x)
        # print(f"[DINOCrossAttentionMLP] After fc_layer4: {x.shape}")
        output = self.fc_layer5(x)
        # print(f"[DINOCrossAttentionMLP] Output shape: {output.shape}")
        return output

import matplotlib.pyplot as plt
import os

WEIGHT_SAVING_STEP = 10
DPI = 120
FIGURE_SIZE_PIXEL = [2490, 1490]
FIGURE_SIZE = [fsp / DPI for fsp in FIGURE_SIZE_PIXEL]

def plot_graph(training_losses, train_accuracies, figure_path=None, start_plot=0, end_plot=None):
    if end_plot is None or end_plot > len(training_losses):
        end_plot = len(training_losses)

    epochs = range(start_plot + 1, end_plot + 1)

    # ===== Training Loss =====
    plt.figure(figsize=FIGURE_SIZE, dpi=DPI)
    plt.scatter(epochs, training_losses[start_plot:end_plot], color='blue', label='Training Loss')
    plt.plot(epochs, training_losses[start_plot:end_plot], color='cyan', linestyle='-', label='Loss Trend')
    plt.title("Training Loss")
    plt.xlabel("Epochs")
    plt.ylabel("Loss (scaled)")
    plt.legend()

    lowest_loss = min(training_losses[start_plot:end_plot])
    for i, loss in enumerate(training_losses[start_plot:end_plot], start=start_plot+1):
        if (i % WEIGHT_SAVING_STEP == 0) or (i == end_plot):
            plt.annotate(str(round(loss, 6)), xy=(i, loss))

    plt.text(0, plt.gca().get_ylim()[1], f'Lowest Loss: {lowest_loss:.6f}')

    if figure_path is not None:
        plt.savefig(os.path.join(figure_path, 'Training_loss.png'))
    plt.show()

    # ===== Training Accuracy =====
    plt.figure(figsize=FIGURE_SIZE, dpi=DPI)
    plt.plot(epochs, train_accuracies[start_plot:end_plot], color='green', linestyle='-', marker='o',
             label='Training Accuracy')
    plt.title("Training Accuracy")
    plt.xlabel("Epochs")
    plt.ylabel("Accuracy (%)")
    plt.legend()

    for i, acc in enumerate(train_accuracies[start_plot:end_plot], start=start_plot+1):
        if (i % WEIGHT_SAVING_STEP == 0) or (i == end_plot):
            plt.annotate(f"{round(acc, 2)}", xy=(i, acc))

    if figure_path is not None:
        plt.savefig(os.path.join(figure_path, 'Training_accuracy.png'))
    plt.show()

import os
import torch
import numpy as np
from torch.utils.data import DataLoader
from torchvision import transforms

# === DINO Cross Attention Model ===
from groundingdino.util.slconfig import SLConfig
from groundingdino.models import build_model

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f'Using device: {DEVICE}')

data_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])


SPLIT_DATA_PATH = '/content/drive/MyDrive/Spot_IL/Real Test Data Lab'
LABEL_PATH = os.path.join(SPLIT_DATA_PATH, 'train/labels.npy')
TRAIN_PATH = os.path.join(SPLIT_DATA_PATH, 'train')

WEIGHT_PATH = os.path.join(SPLIT_DATA_PATH, 'weights/dino_mlp_encoder')
os.makedirs(WEIGHT_PATH, exist_ok=True)

FIGURE_PATH = os.path.join(SPLIT_DATA_PATH, 'Results/dino_mlp_encoder')
os.makedirs(FIGURE_PATH, exist_ok=True)

full_dataset = SPOTDataLoader(
    root_dir=TRAIN_PATH,
    labels_file=LABEL_PATH,
    transform=data_transforms
)
print(f"Total training samples: {len(full_dataset)}")

BATCH_SIZE = 4
train_dataloader = DataLoader(full_dataset, batch_size=BATCH_SIZE, shuffle=True)

LEARNING_RATE = 1e-3
NUM_EPOCHS = 500
LOSS_SCALE = 1e3
TOLERANCE = 1e-1
loss_fn = torch.nn.MSELoss()

# === DINO-based model  ===
config_file = "groundingdino/config/GroundingDINO_SwinT_OGC.py"
weight_file = "weights/groundingdino_swint_ogc.pth"

model = DINOCrossAttentionMLP(
    config_file=config_file,
    weight_file=weight_file,
    num_cameras=4,
    embed_dim=256,
    device=DEVICE
).to(DEVICE)

# === Only optimize parameters that require grad ===
optimizer = torch.optim.Adam(
    [p for p in model.parameters() if p.requires_grad],
    lr=LEARNING_RATE
)

training_losses = []
train_accuracies = []

for epoch in range(1, NUM_EPOCHS + 1):
    model.train()
    running_loss = 0.0

    for batch_idx, (current_images, goal_images, labels) in enumerate(train_dataloader):
        current_images = current_images.to(DEVICE)
        goal_images = goal_images.to(DEVICE)
        labels = labels.to(DEVICE)

        text_prompts = ["green chair." for _ in range(current_images.size(0))]

        optimizer.zero_grad()
        output = model(current_images, goal_images, text_prompts)
        loss = loss_fn(output, labels.float()) * LOSS_SCALE
        loss.backward()
        optimizer.step()
        running_loss += loss.item()

    epoch_loss = running_loss / len(train_dataloader)
    training_losses.append(epoch_loss)
    print(f"Epoch {epoch}/{NUM_EPOCHS} -- Training Loss: {epoch_loss:.6f}")

    # --- Training Accuracy ---
    model.eval()
    train_correct = 0
    train_total = 0
    with torch.no_grad():
        for current_images, goal_images, labels in train_dataloader:
            current_images = current_images.to(DEVICE)
            goal_images = goal_images.to(DEVICE)
            labels = labels.to(DEVICE)
            text_prompts = ["green chair." for _ in range(current_images.size(0))]

            output = model(current_images, goal_images, text_prompts)

            for i in range(output.size(0)):
                error = torch.norm(output[i] - labels[i].float(), p=2).item()
                train_total += 1
                if error < TOLERANCE:
                    train_correct += 1

    train_accuracy = (train_correct / train_total) * 100
    train_accuracies.append(train_accuracy)
    print(f"Epoch {epoch}/{NUM_EPOCHS} -- Training Accuracy: {train_accuracy:.2f}%")

print("Training complete.")