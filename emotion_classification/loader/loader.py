# sys
import os
import h5py
import numpy as np
import cv2
import glob
import re

# torch
from sklearn.model_selection import train_test_split
import torch

def load_data(_path_features, _path_lables, coords, joints,cycles=3, test_size = 0.1):
    # file_feature = os.path.join(_path, 'features' + _ftype + '.h5')
    # file_label = os.path.join(_path, 'labels' + _ftype + '.h5')
    ff = h5py.File(_path_features, 'r')
    fl = h5py.File(_path_lables, 'r')

    data_list = []
    num_samples = len(ff.keys())
    time_steps = 0
    labels = np.empty(num_samples)
    for si in range(num_samples):
        ff_group_key = list(ff.keys())[si]
        data_list.append(list(ff[ff_group_key]))  # Get the data
        time_steps_curr = len(ff[ff_group_key])
        if time_steps_curr > time_steps:
            time_steps = time_steps_curr
        labels[si] = fl[list(fl.keys())[si]][()]

    data = np.empty((num_samples, time_steps*cycles, joints*coords))
    for si in range(num_samples):
        data_list_curr = np.tile(data_list[si], (int(np.ceil(time_steps / len(data_list[si]))), 1))
        for ci in range(cycles):
            data[si, time_steps * ci:time_steps * (ci + 1), :] = data_list_curr[0:time_steps]
    data_train, data_test, labels_train, labels_test = train_test_split(data, labels, test_size = test_size)
    
    return data, labels, data_train, labels_train, data_test, labels_test

def load_data_multiview(_path_features, _path_lables, coords, joints, cycles=3, test_size = 0.1):
    feature_files = glob.glob(_path_features)
    label_files = glob.glob(_path_lables)
    print(f'---> Number of files = {len(feature_files)}')
    # sorting files so that features and labels files match
    feature_files.sort()
    label_files.sort()
        
    angle_regex = re.compile('(\d*).h5')
    folder_regex = re.compile('(\w*)\/')
    
    all_data_train = []
    all_data_test = []
    all_labels_train = []
    all_labels_test = []
    all_angles_train = []
    all_angles_test = []
    
    for feature_file, label_file in zip(feature_files, label_files):
        ff = h5py.File(feature_file, 'r')
        fl = h5py.File(label_file, 'r')
        angle = int(angle_regex.search(feature_file).group(1))
        folder = folder_regex.findall(feature_file)[-1]
        print(f"--->> processing - {folder} - {angle}")
        
        data_list = []
        num_samples = len(ff.keys())
        time_steps = 0
        labels = np.empty(num_samples)
        for si in range(num_samples):
            ff_group_key = list(ff.keys())[si]
            data_list.append(list(ff[ff_group_key]))  # Get the data
            time_steps_curr = len(ff[ff_group_key])
            if time_steps_curr > time_steps:
                time_steps = time_steps_curr
            labels[si] = fl[list(fl.keys())[si]][()]
        data = np.empty((num_samples, time_steps*cycles, joints*coords))
        for si in range(num_samples):
            data_list_curr = np.tile(data_list[si], (int(np.ceil(time_steps / len(data_list[si]))), 1))
            for ci in range(cycles):
                data[si, time_steps * ci:time_steps * (ci + 1), :] = data_list_curr[0:time_steps]
        data_train, data_test, labels_train, labels_test = train_test_split(data,
                                                                            labels,
                                                                            test_size = test_size)

        all_data_train.extend(data_train)
        all_data_test.extend(data_test)
        all_labels_train.extend(labels_train)
        all_labels_test.extend(labels_test)
        all_angles_train.extend([angle]*len(labels_train))
        all_angles_test.extend([angle]*len(labels_test))
        
    return data, labels, \
                all_data_train, all_labels_train, \
                all_data_test, all_labels_test, \
                all_angles_train, all_angles_test

def scale(_data):
    data_scaled = _data.astype('float32')
    data_max = np.max(data_scaled)
    data_min = np.min(data_scaled)
    data_scaled = (_data-data_min)/(data_max-data_min)
    return data_scaled, data_max, data_min


# descale generated data
def descale(data, data_max, data_min):
    data_descaled = data*(data_max-data_min)+data_min
    return data_descaled


def to_categorical(y, num_classes):
    """ 1-hot encodes a tensor """
    return np.eye(num_classes, dtype='uint8')[y]


class TrainTestLoader(torch.utils.data.Dataset):

    def __init__(self, data, label, joints, coords, num_classes):
        # data: N C T J
        self.data = data

        # load label
        self.label = label
        
        self.joints = joints
        self.coords = coords

    def __len__(self):
        return len(self.label)

    def __getitem__(self, index):
        # data: N C T J
        data_numpy = np.asarray(self.data[index])
        data_numpy = np.reshape(data_numpy,
                               (1,
                                data_numpy.shape[0],
                                self.joints,
                                self.coords,
                                1))
        data_numpy = np.moveaxis(data_numpy, [1, 2, 3], [2, 3, 1])
        self.N, self.C, self.T, self.J, self.M = data_numpy.shape
        label = self.label[index]
        return data_numpy, label
    
class TrainTestLoader_vscnn(torch.utils.data.Dataset):

    def __init__(self, data, label, joints, coords, num_classes):
        # data: N C T J
        self.data = data

        # load label
        self.label = label
        
        self.joints = joints
        self.coords = coords

    def __len__(self):
        return len(self.label)
    
    def _convert_skeletion_to_image(self, data_numpy):
        # (1, 3, 75, 16, 1)
        data_numpy = np.squeeze(data_numpy, axis = 0)
        data_max = np.max(data_numpy, (1,2,3))
        data_min = np.min(data_numpy, (1,2,3))
        img_data = np.zeros((data_numpy.shape[1],
                             data_numpy.shape[2],
                             data_numpy.shape[0]))

        img_data[:,:,0] = (data_max[0] - data_numpy[0,:,:,0]) * ( 255 / (data_max[0] - data_min[0]) )
        img_data[:,:,1] = (data_max[1] - data_numpy[1,:,:,0]) * ( 255 / (data_max[1] - data_min[1]) )
        img_data[:,:,2] = (data_max[2] - data_numpy[2,:,:,0]) * ( 255 / (data_max[2] - data_min[2]) )
        
#        img_data[:,:,0] = np.divide(img_data[:,:,0], img_data[:,:,2]+1e-9)
#        img_data[:,:,1] = np.divide(img_data[:,:,1], img_data[:,:,2]+1e-9)
#        img_data[:,:,2] = np.divide(img_data[:,:,2], img_data[:,:,2]+1e-9)
        
        img_data = cv2.resize(img_data, (244,244))
        
#        cv2.imshow("testframe", img_data)
#        cv2.waitKey(10)
#        cv2.imwrite(f"../temp/{np.random.randint(low=1, high=100)}.png",
#                               img_data)
        
        return img_data
        
    def __getitem__(self, index):
        
        # data: N C T J
        data_numpy = np.asarray(self.data[index])
        data_numpy = np.reshape(data_numpy,
                               (1,
                                data_numpy.shape[0],
                                self.joints,
                                self.coords,
                                1))
        data_numpy = np.moveaxis(data_numpy, [1, 2, 3], [2, 3, 1])
        self.N, self.C, self.T, self.J, self.M = data_numpy.shape
        label = self.label[index]
        img_data = self._convert_skeletion_to_image(data_numpy)
        
        return img_data, label