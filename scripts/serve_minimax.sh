#!/bin/bash
# 设置环境变量
export VLLM_USE_MODELSCOPE=true
# export TIKTOKEN_ENCODINGS_BASE="/inspire/hdd/project/security-defense-and-attack/25015/encodings"
# # 启动API服务
vllm serve /inspire/hdd/project/security-defense-and-attack/public/model_hub/MiniMax-M2.1 \
  --served-model-name MiniMax-M2.1 \
  --data-parallel-size 8 \
  --enable-expert-parallel \
   --max-model-len 12800 \
  --tool-call-parser minimax_m2 \
  --reasoning-parser minimax_m2_append_think  \
  --enable-auto-tool-choice \
  --trust-remote-code \
  --load-format fastsafetensors
