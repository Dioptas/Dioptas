#!/bin/sh
python -m cProfile -o profile.data Py2DeX_loaded.py
snakeviz profile.data &