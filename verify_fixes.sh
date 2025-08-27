#!/bin/bash
# Verification script for A5/F5.5 fixes

echo "=== A5/F5.5 Fix Verification ==="
echo "Current branch: $(git branch --show-current)"
echo "Current commit: $(git rev-parse HEAD)"
echo ""

echo "1. Provider Check - Looking for load_dataset calls:"
echo "---------------------------------------------------"
grep -n "load_dataset" apex/eval/providers/swe_lite.py | head -10
echo ""

echo "2. Checking for _load_swe_dataset helper method:"
echo "-------------------------------------------------"
grep -n "def _load_swe_dataset" apex/eval/providers/swe_lite.py
echo ""

echo "3. Checking where helper is called:"
echo "------------------------------------"
grep -n "self._load_swe_dataset" apex/eval/providers/swe_lite.py
echo ""

echo "4. Decision Packet Header Check:"
echo "---------------------------------"
head -8 docs/A5/F5.5/T5.5_decision.md
echo ""

echo "5. Decision Packet Status/Decision Check:"
echo "------------------------------------------"
grep -n "Status:" docs/A5/F5.5/T5.5_decision.md | head -2
grep -n "Decision:" docs/A5/F5.5/T5.5_decision.md | head -2
echo ""

echo "6. Provenance Check in JSON files:"
echo "-----------------------------------"
echo "lift: $(jq '.metadata.source' docs/A5/artifacts/swe/dev/lift_dev_sample100.json)"
echo "cp_static: $(jq '.source' docs/A5/artifacts/swe/dev/cp_static_dev_sample100.json)"
echo "cp_apex: $(jq '.source' docs/A5/artifacts/swe/dev/cp_apex_dev_sample100.json)"
echo ""

echo "7. Testing provider import:"
echo "----------------------------"
python3 -c "from apex.eval.providers.swe_lite import SWELiteProvider; print('✓ Provider imports successfully')" 2>&1

echo ""
echo "=== Verification Complete ===">