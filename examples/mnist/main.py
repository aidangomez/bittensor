"""Training a MNIST Neuron.

This file demonstrates a training pipeline for an MNIST Neuron.

Example:
        $ python examples/mnist/main.py
"""

import bittensor
from bittensor.synapses.ffnn import FFNNSynapse, FFNNConfig

import argparse
from loguru import logger
import math
import time
import torch
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
import traceback

def main():
    argparser = argparse.ArgumentParser()
     
    # Additional training params.
    batch_size_train = 64
    batch_size_test = 64
    learning_rate = 0.05
    momentum = 0.9
    log_interval = 10
    epoch = 0
    best_test_loss = math.inf
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
   
    # Setup Bittensor.
    # Create background objects.
    # Connect the metagraph.
    # Start the axon server.
    bittensor.init( argparser )
    bittensor.start()

    # Build local synapse to serve on the network.
    model_config = FFNNConfig()
    model = FFNNSynapse(model_config)
    model.to( device ) # Set model to device.
    bittensor.serve( model.deepcopy() )

    # Build the optimizer.
    optimizer = optim.SGD(model.parameters(), lr=learning_rate, momentum=momentum)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10.0, gamma=0.1)

    # Load (Train, Test) datasets into memory.
    config = bittensor.get_config()
    train_data = torchvision.datasets.MNIST(root = config.datapath + "datasets/", train=True, download=True, transform=transforms.ToTensor())
    trainloader = torch.utils.data.DataLoader(train_data, batch_size = batch_size_train, shuffle=True, num_workers=2)
    test_data = torchvision.datasets.MNIST(root = config.datapath + "datasets/", train=False, download=True, transform=transforms.ToTensor())
    testloader = torch.utils.data.DataLoader(test_data, batch_size = batch_size_test, shuffle=False, num_workers=2)
    # Train loop: Single threaded training of MNIST.
    def train(model, epoch):
        # Turn on Dropoutlayers BatchNorm etc.
        model.train()
        last_log = time.time()
        for batch_idx, (images, targets) in enumerate(trainloader):
            optimizer.zero_grad() # Clear lingering gradients if present.
            
            # Forward pass.
            images = images.to(device)
            targets = torch.LongTensor(targets).to(device)
            output = model(images, targets, remote = True)

            # Backprop.
            output.loss.backward()
            optimizer.step() # Apply gradient step.
            global_step += 1
                            
            # Logs:
            if (batch_idx + 1) % log_interval == 0: 
                n = len(train_data)
                max_logit = output.remote_target.data.max(1, keepdim=True)[1]
                correct = max_logit.eq( targets.data.view_as(max_logit) ).sum()
                loss_item  = output.remote_target_loss.item()
                processed = ((batch_idx + 1) * batch_size_train)
                
                progress = (100. * processed) / n
                accuracy = (100.0 * correct) / batch_size_train
                logger.info('Train Epoch: {} [{}/{} ({:.0f}%)] Balance: {:.2f}     Block: {}    GS: {}    Local Loss: {:.6f}    Accuracy: {:.6f}    nP: {}'', 
                    epoch, processed, n, progress, bittensor.balance(), bittensor.height(), global_step, loss_item, accuracy, len(bittensor.metagraph.peers()))
                bittensor.log_output(global_step, output)
                last_log = time.time()

    # Test loop.
    # Evaluates the local model on the hold-out set.
    # Returns the test_accuracy and test_loss.
    def test( model: bittensor.Synapse):
        
        # Turns off Dropoutlayers, BatchNorm etc.
        model.eval()
        
        # Turns off gradient computation for inference speed up.
        with torch.no_grad():
        
            loss = 0.0
            correct = 0.0
            for _, (images, labels) in enumerate(testloader):                
                
                images = images.to(device)
                # Labels to Tensor
                labels = torch.LongTensor(labels).to(device)

                # Compute full pass and get loss.
                outputs = model.forward(images, labels, remote = False)
                loss = loss + outputs.local_target_loss.item()
                
                # Count accurate predictions.
                max_logit = outputs.local_target.data.max(1, keepdim=True)[1]
                correct = correct + max_logit.eq( labels.data.view_as(max_logit) ).sum()
        
        # # Log results.
        n = len(test_data)
        loss /= n
        accuracy = (100. * correct) / n
        logger.info('Test set: Avg. loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(loss, correct, n, accuracy))  
        bittensor.tbwriter.add_scalar('test loss', loss, global_step)
        return loss, accuracy
    
    while True:
        try:
            # Train model
            train( model, epoch )
            scheduler.step()
            # Test model.
            test_loss, _ = test( model )
        
            # Save best model. 
            if test_loss < best_test_loss:
                # Update best loss.
                best_test_loss = test_loss
                
                # Save and serve the new best local model.
                logger.info( 'Saving/Serving model: epoch: {}, loss: {}, path: {}', epoch, test_loss, config.logdir + '/model.torch' )
                torch.save( {'epoch': epoch, 'model': model.state_dict(), 'test_loss': test_loss}, config.logdir + '/model.torch' )
                bittensor.serve( model.deepcopy() )

            epoch += 1

        except Exception as e:
            traceback.print_exc()
            logger.error(e)
            bittensor.stop()
            break

if __name__ == "__main__":
    main()
