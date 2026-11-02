#!/bin/bash
cd "$(dirname "$0")"
python3 render.py CAM_Hero   renders/01_hero.png        100 128 1600 2000 > renders/log_hero.txt 2>&1
python3 render.py CAM_Macro  renders/02_tourbillon.png  100 112 1920 1080 > renders/log_macro.txt 2>&1
python3 render.py CAM_Spiral renders/03_spiral.png      100 112 1920 1080 > renders/log_spiral.txt 2>&1
python3 render.py CAM_Back   renders/04_back.png        100 96  1600 2000 > renders/log_back.txt 2>&1
echo ALLDONE
