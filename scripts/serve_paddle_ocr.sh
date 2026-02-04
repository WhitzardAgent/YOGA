CUDA_VISIBLE_DEVICES=6,7 vllm serve /inspire/hdd/global_user/25015/models/paddleocr_vl \
    --trust-remote-code \
    --max-num-batched-tokens 16384 \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0 \
    --host 0.0.0.0 \
    --port 8011