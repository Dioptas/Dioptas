#!/bin/sh
python -m cProfile -o profile.data Dioptas_loaded.py
snakeviz profile.data &