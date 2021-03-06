
import bittensor.serialization as serialization
import bittensor.utils.serialization_utils as serialization_utils
from bittensor.config import Config
from bittensor.subtensor.interface import Keypair
from random import randrange

from datasets import load_dataset
from bittensor.synapses.gpt2 import nextbatch

import bittensor.bittensor_pb2 as bittensor_pb2
import torchvision.transforms as transforms
import torch
import unittest
import bittensor
import torchvision
import pytest
from munch import Munch

class TestSerialization(unittest.TestCase):
    config = None

    def setUp(self):
        config = {'session':
                      {'datapath': 'data/', 'learning_rate': 0.01, 'momentum': 0.9, 'batch_size_train': 64,
                       'batch_size_test': 64, 'log_interval': 10, 'sync_interval': 100, 'priority_interval': 100,
                       'name': 'mnist', 'trial_id': '1608070667'},
                  'synapse': {'target_dim': 10},
                  'dendrite': {'key_dim': 100, 'topk': 10, 'stale_emit_filter': 10000, 'pass_gradients': True,
                               'timeout': 0.5,
                               'do_backoff': True, 'max_backoff': 100},
                  'axon': {'local_port': 8091, 'external_ip': '191.97.53.53'},
                  'nucleus': {'max_workers': 5, 'queue_timeout': 5, 'queue_maxsize': 1000},
                  'metagraph': {'chain_endpoint': '206.189.254.5:12345', 'stale_emit_filter': 10000},
                  'meta_logger': {'log_dir': 'data/'},
                  'neuron': {'keyfile': None, 'keypair': None}
                  }

        config = Munch.fromDict(config)
        mnemonic = Keypair.generate_mnemonic()
        keypair = Keypair.create_from_mnemonic(mnemonic)
        config.neuron.keypair = keypair

        self.keypair = Keypair.create_from_mnemonic(mnemonic)

    def test_serialize(self):
        for _ in range(10):
            tensor_a = torch.rand([12, 23])
            serializer = serialization.get_serializer( serialzer_type = bittensor_pb2.Serializer.MSGPACK )
            content = serializer.serialize(tensor_a, modality = bittensor_pb2.Modality.TENSOR, from_type = bittensor_pb2.TensorType.TORCH)
            tensor_b = serializer.deserialize(content, to_type = bittensor_pb2.TensorType.TORCH)
            torch.all(torch.eq(tensor_a, tensor_b))
            
    def test_serialize_object_type_exception(self):
        # Let's grab some image data
        data = torchvision.datasets.MNIST(root = 'data/datasets/', train=True, download=True, transform=transforms.ToTensor())
        
        # Let's grab a random image, and try and de-serialize it incorrectly.
        image = data[randrange(len(data))][0]

        serializer = serialization.get_serializer( serialzer_type = bittensor_pb2.Serializer.MSGPACK )
        with pytest.raises(serialization.SerializationTypeNotImplementedException):
            serializer.serialize(image, modality = bittensor_pb2.Modality.IMAGE, from_type = 11)

    def test_deserialization_object_type_exception(self):
        data = torch.rand([12, 23])
        
        serializer = serialization.get_serializer( serialzer_type = bittensor_pb2.Serializer.MSGPACK )
        tensor_message = serializer.serialize(data, modality = bittensor_pb2.Modality.TEXT, from_type = bittensor_pb2.TensorType.TORCH)

        with pytest.raises(serialization.SerializationTypeNotImplementedException):
            serializer.deserialize(tensor_message, to_type = 11)
    
    def test_serialize_deserialize_image(self):
        # Let's grab some image data
        data = torchvision.datasets.MNIST(root = 'data/datasets/', train=True, download=True, transform=transforms.ToTensor())
        
        # Let's grab a random image, and give it a crazy type to break the system
        image = data[randrange(len(data))][0]

        serializer = serialization.get_serializer( serialzer_type = bittensor_pb2.Serializer.MSGPACK )
        serialized_image_tensor_message = serializer.serialize(image, modality = bittensor_pb2.Modality.IMAGE, from_type = bittensor_pb2.TensorType.TORCH)
        
        assert image.requires_grad == serialized_image_tensor_message.requires_grad
        assert list(image.shape) == serialized_image_tensor_message.shape
        assert serialized_image_tensor_message.modality == bittensor_pb2.Modality.IMAGE
        assert serialized_image_tensor_message.dtype != bittensor_pb2.DataType.UNKNOWN

        deserialized_image_tensor_message = serializer.deserialize(serialized_image_tensor_message, to_type = bittensor_pb2.TensorType.TORCH)
        assert serialized_image_tensor_message.requires_grad == deserialized_image_tensor_message.requires_grad
        assert serialized_image_tensor_message.shape == list(deserialized_image_tensor_message.shape)
        assert serialization_utils.torch_dtype_to_bittensor_dtype(deserialized_image_tensor_message.dtype) != bittensor_pb2.DataType.UNKNOWN

        assert torch.all(torch.eq(deserialized_image_tensor_message, image))


    def test_serialize_deserialize_text(self):
        # Let's create some text data
        words = ["This", "is", "a", "word", "list"]
        max_l = 0
        ts_list = []
        for w in words:
            ts_list.append(torch.ByteTensor(list(bytes(w, 'utf8'))))
            max_l = max(ts_list[-1].size()[0], max_l)

        data = torch.zeros((len(ts_list), max_l), dtype=torch.int64)
        for i, ts in enumerate(ts_list):
            data[i, 0:ts.size()[0]] = ts

        serializer = serialization.get_serializer( serialzer_type = bittensor_pb2.Serializer.MSGPACK )
        serialized_data_tensor_message = serializer.serialize(data, modality = bittensor_pb2.Modality.TEXT, from_type = bittensor_pb2.TensorType.TORCH)
       
        assert data.requires_grad == serialized_data_tensor_message.requires_grad
        assert list(data.shape) == serialized_data_tensor_message.shape
        assert serialized_data_tensor_message.modality == bittensor_pb2.Modality.TEXT
        assert serialized_data_tensor_message.dtype != bittensor_pb2.DataType.UNKNOWN

        deserialized_data_tensor_message = serializer.deserialize(serialized_data_tensor_message, to_type = bittensor_pb2.TensorType.TORCH)
        assert serialized_data_tensor_message.requires_grad == deserialized_data_tensor_message.requires_grad
        assert serialized_data_tensor_message.shape == list(deserialized_data_tensor_message.shape)
        assert serialization_utils.torch_dtype_to_bittensor_dtype(deserialized_data_tensor_message.dtype) != bittensor_pb2.DataType.UNKNOWN

        assert torch.all(torch.eq(deserialized_data_tensor_message, data))

    
    def test_serialize_deserialize_tensor(self):
        data = torch.rand([12, 23])

        serializer = serialization.get_serializer( serialzer_type = bittensor_pb2.Serializer.MSGPACK )
        serialized_tensor_message = serializer.serialize(data, modality = bittensor_pb2.Modality.TENSOR, from_type = bittensor_pb2.TensorType.TORCH)
       
        assert data.requires_grad == serialized_tensor_message.requires_grad
        assert list(data.shape) == serialized_tensor_message.shape
        assert serialized_tensor_message.modality == bittensor_pb2.Modality.TENSOR
        assert serialized_tensor_message.dtype == bittensor_pb2.DataType.FLOAT32

        deserialized_tensor_message = serializer.deserialize(serialized_tensor_message, to_type = bittensor_pb2.TensorType.TORCH)
        assert serialized_tensor_message.requires_grad == deserialized_tensor_message.requires_grad
        assert serialized_tensor_message.shape == list(deserialized_tensor_message.shape)
        assert serialization_utils.torch_dtype_to_bittensor_dtype(deserialized_tensor_message.dtype) == bittensor_pb2.DataType.FLOAT32

        assert torch.all(torch.eq(deserialized_tensor_message, data))

    
    def test_bittensor_dtype_to_torch_dtype(self):
        with pytest.raises(serialization.DeserializationException):
            serialization_utils.bittensor_dtype_to_torch_dtype(11)