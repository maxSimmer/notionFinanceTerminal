#!/bin/bash
#! point at budget.py for single file execution
cd /home/max/Projects/notionFinance
source /home/max/budget-env/bin/activate
python3 -m terminalSplit
exec bash
