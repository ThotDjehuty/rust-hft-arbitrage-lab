#!/usr/bin/env bash
set -e
cd /app
jupyter notebook --ip=0.0.0.0 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''
