#!/bin/sh
# git clone
git clone https://github.com/NVIDIA/DeepLearningExamples.git

# copy download coco dataset script 
chmod +x download_coco2017tf_dataset.sh
cp download_coco2017tf_dataset.sh ./DeepLearningExamples/TensorFlow/Detection/SSD/

# set working directory
cd DeepLearningExamples/TensorFlow/Detection/SSD/

# build docker
docker build . -t nvidia_ssd

# run the script
./download_coco2017tf_dataset.sh nvidia_ssd ./data/coco2017_tfrecords ./checkpoints

# run docker
nvidia-docker run --gpus all --rm --shm-size=1g --ulimit memlock=-1 --ulimit stack=67108864 -v ${PWD}/data/coco2017_tfrecords:/data/coco2017_tfrecords -v ${PWD}/checkpoints:/checkpoints --ipc=host nvidia_ssd bash ./examples/SSD320_FP16_8GPU.sh /checkpoints