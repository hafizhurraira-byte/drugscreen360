from fastapi import APIRouter

router = APIRouter(tags=["examples-demo"])

LIMITATION = "Demo data is for UI demonstration only. It is not a complete or current live database result."


SINGLE_MOLECULE_EXAMPLES = [
    {"name": "Aspirin", "input_query": "Aspirin", "input_type": "name", "description": "Classic analgesic and anti-inflammatory reference compound."},
    {"name": "Caffeine", "input_query": "Caffeine", "input_type": "name", "description": "Small CNS-active stimulant example."},
    {"name": "Ibuprofen", "input_query": "Ibuprofen", "input_type": "name", "description": "NSAID example for oral drug-like screening."},
    {"name": "Metformin", "input_query": "Metformin", "input_type": "name", "description": "Highly polar antidiabetic drug example."},
    {"name": "Imatinib", "input_query": "Imatinib", "input_type": "name", "description": "Kinase inhibitor example."},
    {"name": "Tamoxifen", "input_query": "Tamoxifen", "input_type": "name", "description": "Endocrine therapy example."},
    {"name": "Erlotinib", "input_query": "Erlotinib", "input_type": "name", "description": "EGFR inhibitor example."},
    {"name": "Acetaminophen", "input_query": "Acetaminophen", "input_type": "name", "description": "Common analgesic example."},
]

DRUG_FINDER_EXAMPLES = [
    {"target_query": item, "context": "Example target query for ChEMBL candidate retrieval."}
    for item in ["EGFR", "ESR1", "ERBB2", "PIK3CA", "COX2", "JAK2", "BRAF", "VEGFA", "ROCK2"]
]

DISEASE_FINDER_EXAMPLES = [
    {"disease_query": item, "context": "Example disease query for Open Targets association review."}
    for item in [
        "breast cancer",
        "lung cancer",
        "Alzheimer disease",
        "idiopathic pulmonary fibrosis",
        "diabetes",
        "colorectal cancer",
        "prostate cancer",
        "rheumatoid arthritis",
    ]
]

SIMILARITY_EXAMPLES = [
    {"reference_molecule": item, "input_type": "name", "source": "auto", "threshold": 70}
    for item in ["Aspirin", "Caffeine", "Ibuprofen", "Metformin", "Imatinib", "Erlotinib"]
]

WORKFLOWS = [
    {
        "name": "Screen Aspirin",
        "workflow_type": "single_molecule",
        "description": "Prepare Aspirin screening as a drug-name input.",
        "action": {"tab": "screening", "query": "Aspirin", "input_type": "name"},
    },
    {
        "name": "Find EGFR Candidates",
        "workflow_type": "target_to_candidate",
        "description": "Prepare Drug Finder with EGFR and prefer the human single-protein ChEMBL target when live results load.",
        "action": {"tab": "finder", "target_query": "EGFR"},
    },
    {
        "name": "Breast Cancer to Candidate Screening",
        "workflow_type": "disease_to_candidate",
        "description": "Prepare Disease Finder with breast cancer and show ranked targets before molecule retrieval.",
        "action": {"tab": "disease", "disease_query": "breast cancer"},
    },
    {
        "name": "Caffeine Similarity Search",
        "workflow_type": "similarity_to_candidate",
        "description": "Prepare Similarity Finder with Caffeine, source Auto, and threshold 70.",
        "action": {"tab": "similarity", "query": "Caffeine", "input_type": "name", "source": "auto", "threshold": 70},
    },
]


DEMO_EGFR_CANDIDATES = [
    {
        "candidate_rank": 1,
        "molecule_chembl_id": "CHEMBL553",
        "compound_name": "Erlotinib",
        "canonical_smiles": "COCCOc1cc2ncnc(Nc3cccc(Cl)c3)c2cc1OCCOC",
        "activity_type": "IC50",
        "activity_value": 2.0,
        "activity_units": "nM",
        "target_name": "Epidermal growth factor receptor",
        "target_chembl_id": "CHEMBL203",
        "source": "Demo data",
        "ranking_reason": "Demo EGFR candidate. Use live ChEMBL for current evidence.",
    },
    {
        "candidate_rank": 2,
        "molecule_chembl_id": "CHEMBL939",
        "compound_name": "Gefitinib",
        "canonical_smiles": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",
        "activity_type": "IC50",
        "activity_value": 10.0,
        "activity_units": "nM",
        "target_name": "Epidermal growth factor receptor",
        "target_chembl_id": "CHEMBL203",
        "source": "Demo data",
        "ranking_reason": "Demo EGFR candidate. Use live ChEMBL for current evidence.",
    },
]

DEMO_BREAST_CANCER_TARGETS = [
    {
        "disease_target_rank": 1,
        "target_id": "ENSG00000146648",
        "approved_symbol": "EGFR",
        "approved_name": "epidermal growth factor receptor",
        "biotype": "protein_coding",
        "overall_association_score": 0.78,
        "known_drug_score": 0.71,
        "genetic_association_score": 0.44,
        "suggested_chembl_query": "EGFR",
        "ranking_reason": "Demo ranked target. Open Targets live data should be used for current prioritization.",
    },
    {
        "disease_target_rank": 2,
        "target_id": "ENSG00000091831",
        "approved_symbol": "ESR1",
        "approved_name": "estrogen receptor 1",
        "biotype": "protein_coding",
        "overall_association_score": 0.74,
        "known_drug_score": 0.82,
        "genetic_association_score": 0.38,
        "suggested_chembl_query": "ESR1",
        "ranking_reason": "Demo ranked target. Open Targets live data should be used for current prioritization.",
    },
]

DEMO_SIMILARITY = {
    "aspirin": [
        {
            "similarity_rank": 1,
            "compound_name": "Salicylic acid",
            "pubchem_cid": 338,
            "canonical_smiles": "C1=CC=C(C(=C1)C(=O)O)O",
            "similarity_score": 76.2,
            "source": "Demo data",
            "ranking_reason": "Demo analog record. Use live similarity search for current database results.",
        }
    ],
    "caffeine": [
        {
            "similarity_rank": 1,
            "compound_name": "Theophylline",
            "pubchem_cid": 2153,
            "canonical_smiles": "CN1C=NC2=C1C(=O)NC(=O)N2C",
            "similarity_score": 82.4,
            "source": "Demo data",
            "ranking_reason": "Demo analog record. Use live similarity search for current database results.",
        }
    ],
}


@router.get("/examples")
def examples():
    return {
        "single_molecule": SINGLE_MOLECULE_EXAMPLES,
        "drug_finder": DRUG_FINDER_EXAMPLES,
        "disease_finder": DISEASE_FINDER_EXAMPLES,
        "similarity_finder": SIMILARITY_EXAMPLES,
        "limitation": LIMITATION,
    }


@router.get("/examples/workflows")
def workflow_templates():
    return {"workflows": WORKFLOWS, "limitation": LIMITATION}


@router.get("/demo/egfr-candidates")
def demo_egfr_candidates():
    return {"data_source": "demo", "candidates": DEMO_EGFR_CANDIDATES, "limitation": LIMITATION}


@router.get("/demo/breast-cancer-targets")
def demo_breast_cancer_targets():
    return {"data_source": "demo", "targets": DEMO_BREAST_CANCER_TARGETS, "limitation": LIMITATION}


@router.get("/demo/similarity/{reference}")
def demo_similarity(reference: str):
    key = reference.strip().lower()
    return {"data_source": "demo", "reference": key, "similar_compounds": DEMO_SIMILARITY.get(key, []), "limitation": LIMITATION}
