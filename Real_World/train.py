import torch, os
import numpy as np
from torchvision import transforms
from torch.utils.data import DataLoader
from SPOT_SingleStep_DataLoader import SPOT_SingleStep_DataLoader
from Resnet18MLP5 import SharedResNet18MLP5
from plot_graph import plot_graph

CONTINUE = 0   # Start fresh at 0

# Setup Destination
DATASET_NAME = 'map01_01'
WEIGHT_FOLDER_NAME = 'lr1e-4'
MODEL_NAME = 'ResNet18MLP5'

SCRIPT_PATH = os.path.dirname(__file__)
DATASET_PATH = os.path.join(SCRIPT_PATH, f'{DATASET_NAME}')
if not os.path.exists(DATASET_PATH):
    print('Dataset does not exist !')
    exit()

WEIGHT_PATH = os.path.join(SCRIPT_PATH, f'weights/{MODEL_NAME}_{DATASET_NAME}/{WEIGHT_FOLDER_NAME}/')
if not os.path.exists(WEIGHT_PATH):
    os.makedirs(WEIGHT_PATH)
FIGURE_PATH = os.path.join(SCRIPT_PATH, f'Results/{MODEL_NAME}_{DATASET_NAME}/{WEIGHT_FOLDER_NAME}/')
if not os.path.exists(FIGURE_PATH):
    os.makedirs(FIGURE_PATH)

# Preprocess for images
data_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

if torch.cuda.is_available():
    
    train_dataset = SPOT_SingleStep_DataLoader(
        dataset_dir = DATASET_PATH,
        transform = data_transforms,
        cuda = True
    )
    DEVICE = 'cuda'
    print('Cuda')

else:
    train_dataset = SPOT_SingleStep_DataLoader(
        dataset_dir = DATASET_PATH,
        transform = data_transforms,
        cuda = False
    )
    DEVICE = 'cpu'
    print('CPU')

# Hyper Parameters
loss_fn = torch.nn.MSELoss()
BATCH_SIZE = 16
LEARNING_RATE = 1e-4

# Training Parameters
WEIGHT_SAVING_STEP = 50
LOSS_SCALE = 1e3

# Validation Parameter
TOLERANCE = 1e-2

# Saving Hyper Param
hyper_params_path = os.path.join(WEIGHT_PATH, 'hyper_params')
hyper_params = {'BATCH_SIZE': BATCH_SIZE, 'LEARNING_RATE': LEARNING_RATE, 'LOSS_SCALE': LOSS_SCALE, 'TOLERANCE': TOLERANCE}
print(f'BATCH_SIZE: {BATCH_SIZE}, LEARNING_RATE: {LEARNING_RATE}, LOSS_SCALE: {LOSS_SCALE}, TOLERANCE: {TOLERANCE}')
np.savez(hyper_params_path, **hyper_params)

# Setup Model
model = SharedResNet18MLP5().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# Tracking Parameters
epoch = CONTINUE + 1
training_loss = 1e6
training_total_loss = 0
training_losses = []   #[training_loss training_average_loss]
tracking_losses_path = os.path.join(FIGURE_PATH, 'training_losses.npy')
accuracies = []
accuracies_path = os.path.join(FIGURE_PATH, 'accuracies.npy')

if CONTINUE > 1:
    lastest_weight_path = os.path.join(WEIGHT_PATH, 'epoch_' + str(CONTINUE) + '.pth')
    model.load_state_dict(torch.load(lastest_weight_path))
    print('Weight Loaded!')
    training_losses = list(np.load(tracking_losses_path))[:CONTINUE]
    accuracies = list(np.load(accuracies_path))[:CONTINUE]
    print('Parameter Loaded!')

train_dataloader = DataLoader(train_dataset, batch_size=BATCH_SIZE)
    
# Train Model
while training_loss > ((TOLERANCE ** 2) * LOSS_SCALE):
    
    model.train()
    running_loss = 0.0
    
    for current_images, goal_image, labels in train_dataloader:
        
        optimizer.zero_grad()
        output = model(current_images, goal_image)
        loss = loss_fn(output, labels) * LOSS_SCALE

        loss.backward()
        optimizer.step()
        running_loss += loss.item()

    training_loss = running_loss / len(train_dataloader)

    # Moving Average
    training_total_loss += training_loss * 5
    training_average_loss = training_total_loss / (len(training_losses) + 5)
    training_total_loss = training_average_loss * (len(training_losses) + 1)

    # Save training loss
    training_losses.append([training_loss, training_average_loss])
    print(f'Epoch {epoch}, Loss: {training_losses[epoch - 1][0]:.6f}, Average Loss: {training_losses[epoch - 1][1]:.6f}', end='; ')
    np.save(tracking_losses_path, training_losses)

    if (epoch % WEIGHT_SAVING_STEP) == 0:
        weight_save_path = os.path.join(WEIGHT_PATH, 'epoch_' + str(epoch) + '.pth')
        torch.save(model.state_dict(), weight_save_path)
        print('Save Weights', end='; ')

    # Valid Model
    model.eval()
    with torch.no_grad():

        num_correct, num_total = 0, 0
        for current_images, goal_image, labels in train_dataloader:
            output = model(current_images, goal_image)
            for i in range(output.shape[0]):
                loss = 0
                for j in range(output.shape[1]):
                    loss += abs(output[i][j] - labels[i][j]).item()
                num_total += 1
                if loss < TOLERANCE:
                    num_correct += 1
        train_accuracy = (num_correct / num_total) * 100

        accuracies.append(train_accuracy)
        print(f'Train Accuracy {accuracies[epoch - 1]:.2f}%')
        np.save(accuracies_path, accuracies)

        epoch += 1

print('Finished Training !')
epoch -= 1

# Save last weight
weight_save_path = os.path.join(WEIGHT_PATH, 'epoch_' + str(epoch) + '.pth')
torch.save(model.state_dict(), weight_save_path)
print('Save Last Weights')

# Plot Training Loss and Accuracies graphs
plot_graph(training_losses, accuracies, weight_save_step=WEIGHT_SAVING_STEP, figure_path=FIGURE_PATH, end_plot=epoch)
