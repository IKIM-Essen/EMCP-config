#!/bin/sh
# git clone
git clone https://github.com/NVIDIA/DeepLearningExamples.git

# copy download ImageNet dataset script 
chmod +x download_ImageNet_dataset.sh
cp download_ImageNet_dataset.sh ./DeepLearningExamples/PyTorch/Classification/GPUNet/

# set working directory
cd DeepLearningExamples/PyTorch/Classification/GPUNet/

# create directory for logs and outputs
mkdir -p logs && mkdir -p output

# run the script
./download_ImageNet_dataset.sh

# build docker
docker build -t gpunet .
docker run --gpus all --rm --network=host --shm-size 600G --ipc=host -v /usr/local/pytorch_GPUNET/DeepLearningExamples/PyTorch/Classification/GPUNet/data:/root/data/imagenet/ gpunet ./train.sh $(nvidia-smi --list-gpus | wc -l) /root/data/imagenet/ --model gpunet_0 --sched step --decay-epochs 2.4 --decay-rate .97 --opt rmsproptf -b 192 --epochs 5 --opt-eps .001 -j 8 --warmup-lr 1e-6 --weight-decay 1e-5 --drop 0.3 --drop-connect 0.2 --model-ema --model-ema-decay 0.9999 --aa rand-m9-mstd0.5 --remode pixel --reprob 0.2 --lr .06 --num-classes 1000 --enable-distill False --crop-pct 1.0 --img-size 320 --amp
