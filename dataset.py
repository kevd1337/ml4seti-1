import os

import ibmseti
import torch
import torch.multiprocessing as multiprocessing

LABELS = [
    'brightpixel',
    'narrowband',
    'narrowbanddrd',
    'noise',
    'squarepulsednarrowband',
    'squiggle',
    'squigglesquarepulsednarrowband'
]

LABEL_TO_ID = {label: label_i for label_i, label in enumerate(LABELS)}

class Subset(object):
    def __init__(self, directory, dataset, start, end, pool_size=8, cache=False,
            minibatch_size=10):
        self.directory = directory
        self.cache = cache
        self.minibatch_size = minibatch_size
        size = len(dataset)
        start = int(size * start)
        end = int(size * end)
        self.pool = multiprocessing.Pool(pool_size)
        self.subset = dataset[start:end]

        self.iter = iter(self.subset)

    def _read(self, guid_and_target):
        guid, target = guid_and_target
        if os.path.isfile('%s%s.pth' % (self.directory, guid)):
            tensor = torch.load('%s%s.pth' % (self.directory, guid))
            return tensor, LABEL_TO_ID[target]
        else:
            raw_file = open('%s%s.dat' % (self.directory, guid), 'rb')
            aca = ibmseti.compamp.SimCompamp(raw_file.read())
            spectrogram = aca.get_spectrogram()
            tensor = torch.from_numpy(spectrogram).float().view(1, 384, 512)
            if self.cache:
                torch.save(tensor, '%s%s.pth' % (self.directory, guid))
            return tensor, LABEL_TO_ID[target]

    def reload(self):
        self.iter = iter(self.subset)

    def __iter__(self):
        return self

    def __next__(self):
        guids = []
        try:
            for _ in range(self.minibatch_size):
                guids.append(next(self.iter))
        except StopIteration:
            if guids == []:
                raise
        return zip(*self.pool.map(self._read, guids))

class Dataset(object):
    """This is an object which takes a directory containing the full dataset.
    When iterated over, this object returns (minibatch, minibatch target) pairs.
    """
    def __init__(self, directory, split=(0.6, 0.2, 0.2), minibatch_size=10,
            pool_size=8, cache=False):
        if not directory.endswith('/'):
            self.directory = '%s/' % directory
        else:
            self.directory = directory
        path = '%spublic_list_primary_v3_full_21june_2017.csv' % self.directory
        lines = open(path, 'r').readlines()[1:]
        dataset = [line.strip().split(',', 1) for line in lines]

        train, valid, test = split
        self.train = Subset(
            directory,
            dataset,
            0.0,
            train,
            minibatch_size=minibatch_size,
            pool_size=pool_size,
            cache=cache)
        self.validate = Subset(
            directory,
            dataset,
            train,
            train+valid,
            minibatch_size=minibatch_size,
            pool_size=pool_size,
            cache=cache)
        self.test = Subset(
            directory,
            dataset,
            train+valid,
            train+valid+test,
            minibatch_size=minibatch_size,
            pool_size=pool_size,
            cache=cache)