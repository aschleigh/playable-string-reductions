# Model environment (separate from the frozen checker environment)

    conda create -p /scratch/ashleyz/headroom_models/env_m2m python=3.10
    env_m2m/bin/pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cu121
    env_m2m/bin/pip install transformers==4.40.0 "numpy<2" miditoolkit pretty-midi==0.2.10 tqdm pyyaml "setuptools<70"
    env_m2m/bin/pip install -e REMI-z                      # Sonata165/REMI-z @ f5213c2
    git clone https://github.com/Sonata165/music2music_code   # @ 8359bbd, used read-only
    git clone https://github.com/jthickstun/anticipation      # @ af37397
    env_m2m/bin/pip install -e anticipation

Full lock: requirements-models-lock.txt. Weights from the Hugging Face Hub:
LongshenOu/m2m_arranger, LongshenOu/m2m_pianist_dur, LongshenOu/m2m_ft (tokenizer),
stanford-crfm/music-medium-800k.
