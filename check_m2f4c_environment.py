from __future__ import annotations

import json
import platform
import sys

import numpy
import pandas

from rdkit import Chem
from rdkit import rdBase
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize import rdMolStandardize

mol = Chem.MolFromSmiles("CCO")

if mol is None:
    raise RuntimeError("RDKit could not parse the ethanol test SMILES.")

canonical_smiles = Chem.MolToSmiles(
    mol,
    canonical=True,
    isomericSmiles=True,
)

molecular_weight = Descriptors.MolWt(mol)

uncharger = rdMolStandardize.Uncharger()
uncharged = uncharger.uncharge(mol)

uncharged_smiles = Chem.MolToSmiles(
    uncharged,
    canonical=True,
    isomericSmiles=True,
)

result = {
    "status": "PASS",
    "python_executable": sys.executable,
    "python_version": sys.version,
    "platform": platform.platform(),
    "numpy_version": numpy.__version__,
    "pandas_version": pandas.__version__,
    "rdkit_version": rdBase.rdkitVersion,
    "rdkit_import_test": "PASS",
    "rdkit_smiles_parse_test": "PASS",
    "rdkit_descriptor_test": "PASS",
    "rdkit_standardization_test": "PASS",
    "test_input_smiles": "CCO",
    "canonical_smiles": canonical_smiles,
    "uncharged_smiles": uncharged_smiles,
    "molecular_weight": molecular_weight,
}

print(json.dumps(result, indent=2))