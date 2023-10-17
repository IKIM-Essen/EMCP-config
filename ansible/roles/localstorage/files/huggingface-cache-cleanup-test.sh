#!/bin/bash
#
# Test the huggingface cache cleanup: 1) download, 2) clean, 3) assert model is gone.

venvdir=huggingface-cleanup-venv
python3 -m venv "$venvdir"
pushd "$venvdir"
. bin/activate
pip install huggingface_hub transformers torch

export HUGGINGFACE_HUB_CACHE=~/tmp/hf-cache/
export HUGGINGFACE_ASSETS_CACHE=~/tmp/hf-cache/
rm -Rf "$HUGGINGFACE_HUB_CACHE" "$HUGGINGFACE_ASSETS_CACHE"

modelName=hf-internal-testing/tiny-bert
huggingface-cli scan-cache | grep $modelName -q && { echo 'FAIL: model should not exist before download'; exit 1; }

python -c "from transformers import AutoModel; AutoModel.from_pretrained('${modelName}')"
huggingface-cli scan-cache | grep $modelName -q || { echo 'FAIL: model should exist after download'; exit 1; }

python huggingface-cache-cleanup.py
huggingface-cli scan-cache | grep $modelName -q || { echo 'FAIL: model should exist because not expired'; exit 1; }

find $HUGGINGFACE_HUB_CACHE -type f -exec touch -d "2023-01-01 14:30:00" {} \;
python huggingface-cache-cleanup.py
huggingface-cli scan-cache | grep $modelName -q && { echo 'FAIL: model should not exist after cleanup'; exit 1; }

deactivate
popd
rm -R "$venvdir"
