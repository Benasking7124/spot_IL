import matplotlib.pyplot as plt
import numpy as np
import os

WEIGHT_SAVING_STEP = 10

def plot_graph(training_losses, accuracies, figure_path=None, fold=0, start_plot=0, end_plot=0):

    if start_plot == end_plot:
        return
    
    # Fill with zero
    for i in range(start_plot):
        training_losses[i] = [0, 0]
        accuracies[i] = [0, 0]

    # Plot Training Loss
    training_loss = [data[0] for data in training_losses]
    average_loss = [data[1] for data in training_losses]

    plt.scatter(range(1, end_plot + 1), training_loss, color='blue', label='Training Loss')
    plt.plot(range(1, end_plot + 1), average_loss, color='cyan', linestyle='-', label='Average Training Loss')
    plt.title(f"Fold {fold} Training Loss")
    plt.xlabel("Epoches")
    plt.ylabel("Loss (1000 radians)")
    plt.legend()

    lowest_loss = training_loss[0]
    for i in range(end_plot):

        if training_loss[i] < lowest_loss:
            lowest_loss = training_loss[i]

        if ((i + 1) % WEIGHT_SAVING_STEP) == 0:
            plt.annotate(str(round(training_loss[i], 6)), xy=((i + 1), training_loss[i]))

    plt.annotate(str(round(training_loss[end_plot - 1], 6)), xy=(end_plot, training_loss[end_plot - 1]))

    plt.text(0, plt.gca().get_ylim()[1], f'Lowest Loss: {lowest_loss: .6f}')

    if figure_path is not None:
        plt.savefig(figure_path + f'Fold_{fold}_Training_loss.png')
        plt.close()

    else:
        plt.show()

    # Plot Accuracy
    train_accuracy = [data[0] for data in accuracies]
    valid_accuracy = [data[1] for data in accuracies]

    plt.plot(range(1, end_plot + 1), train_accuracy, color='blue', linestyle='-', marker='o', label='Training Accuracy')
    plt.plot(range(1, end_plot + 1), valid_accuracy, color='orange', linestyle='-', marker='o', label='Validation Accuracy')
    plt.title("Accuracy")
    plt.xlabel("Epoches")
    plt.ylabel("Acurracy (%)")
    plt.legend()

    for i in range(end_plot):
        if ((i + 1) % WEIGHT_SAVING_STEP) == 0:
            plt.annotate(str(round(train_accuracy[i], 2)), xy=((i + 1), train_accuracy[i]))
            plt.annotate(str(round(valid_accuracy[i], 2)), xy=((i + 1), valid_accuracy[i]))
    plt.annotate(str(round(train_accuracy[end_plot - 1], 2)), xy=(end_plot, train_accuracy[end_plot - 1]))
    plt.annotate(str(round(valid_accuracy[end_plot - 1], 2)), xy=(end_plot, valid_accuracy[end_plot - 1]))

    if figure_path is not None:
        plt.savefig(figure_path + f'Fold_{fold}_Accuracy.png')
        plt.close()
    
    else:
        plt.show()

if __name__ == '__main__':
    WEIGHT_PATH = os.getcwd() + '/weights/FiveResNet18MLP5_initial/lr1e-4_with_scaling/'
    
    hyper_params_path = WEIGHT_PATH + 'hyper_params.npz'
    loaded_params = np.load(hyper_params_path)
    params_dict = {key: loaded_params[key].item() for key in loaded_params}
    print(params_dict)

    NUM_FOLD = 5
    END_PLOT = 0
    START_PLOT = 0

    for i in range(NUM_FOLD):
        fold_path = WEIGHT_PATH + 'fold_' + str(i) + '/'
        TRAINING_LOSSES_PATH = fold_path + 'training_losses.npy'
        ACCURACIES_PATH = fold_path + 'accuracies.npy'

        END_PLOT = len(np.load(TRAINING_LOSSES_PATH))
        training_losses = list(np.load(TRAINING_LOSSES_PATH))[:END_PLOT]
        accuracies = list(np.load(ACCURACIES_PATH))[:END_PLOT]

        plot_graph(training_losses, accuracies, fold=i, start_plot=START_PLOT, end_plot=END_PLOT)