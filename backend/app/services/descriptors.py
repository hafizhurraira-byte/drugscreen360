import base64
from functools import lru_cache
from io import BytesIO

from fastapi import HTTPException
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
from rdkit.Chem import Draw

from app.models.schemas import DescriptorSet


def parse_smiles(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise HTTPException(status_code=422, detail="Invalid SMILES: RDKit could not parse the molecule.")
    return mol


@lru_cache(maxsize=4096)
def calculate_descriptors(smiles: str) -> DescriptorSet:
    mol = parse_smiles(smiles)
    return DescriptorSet(
        molecular_weight=round(Descriptors.MolWt(mol), 3),
        logp=round(Crippen.MolLogP(mol), 3),
        tpsa=round(rdMolDescriptors.CalcTPSA(mol), 3),
        hydrogen_bond_donors=int(Lipinski.NumHDonors(mol)),
        hydrogen_bond_acceptors=int(Lipinski.NumHAcceptors(mol)),
        rotatable_bonds=int(Lipinski.NumRotatableBonds(mol)),
        formal_charge=int(sum(atom.GetFormalCharge() for atom in mol.GetAtoms())),
        ring_count=int(rdMolDescriptors.CalcNumRings(mol)),
        aromatic_ring_count=int(rdMolDescriptors.CalcNumAromaticRings(mol)),
        fraction_csp3=round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
    )


def render_structure_image_base64(smiles: str) -> str:
    mol = parse_smiles(smiles)
    Chem.rdDepictor.Compute2DCoords(mol)
    image = Draw.MolToImage(mol, size=(520, 360))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
